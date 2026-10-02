"""Offline tests execute the completed notebook's actual definitions."""
import ast
import contextlib
import io
import datetime
from enum import Enum
import json
from pathlib import Path
from typing import List, Optional
import unittest
from unittest.mock import patch

import pandas as pd
from pydantic import BaseModel, Field, model_validator, ValidationError
import project_lib
from project_lib import Interest, ChatAgent, call_weather_api_mocked

NOTEBOOK = json.loads(Path('project_starter.ipynb').read_text(encoding='utf-8'))
ns = dict(globals(), client=object(), MODEL='gpt-4.1-mini',
          ITINERARY_REVISION_AGENT_SYSTEM_PROMPT='Offline test')
for i in [5, 7, 8, 13, 17, 18, 19, 20, 21, 22, 25, 27, 28, 30, 33, 34]:
    tree = ast.parse(''.join(NOTEBOOK['cells'][i]['source']))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<notebook>', 'exec'), ns)
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if set(names) & {'VACATION_INFO_DICT', 'ACTIVITY_AND_WEATHER_ARE_COMPATIBLE_SYSTEM_PROMPT',
                             'TRAVELER_FEEDBACK', 'ALL_EVAL_FUNCTIONS'}:
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<notebook>', 'exec'), ns)
    if i == 8:
        ns['vacation_info'] = ns['VacationInfo'].model_validate(ns['VACATION_INFO_DICT'])
    if i == 33:
        ns['ALL_TOOLS'] = [ns[n] for n in ['get_activities_by_date_tool', 'run_evals_tool', 'final_answer_tool']]


def fixture():
    days = []
    for date, indexes in [('2025-06-10', [0, 3]), ('2025-06-11', [1, 3]), ('2025-06-12', [1, 3])]:
        activities = project_lib.call_activities_api_mocked(date, 'AgentsVille')
        days.append(dict(date=date, weather=call_weather_api_mocked(date, 'AgentsVille'),
                         activity_recommendations=[dict(activity=activities[i],
                         reasons_for_recommendation=['Matches traveler interests; rest between events.']) for i in indexes]))
    total = sum(r['activity']['price'] for d in days for r in d['activity_recommendations'])
    return ns['TravelPlan'].model_validate(dict(city='AgentsVille', start_date='2025-06-10',
             end_date='2025-06-12', total_cost=total, itinerary_days=days))


def action(name, **arguments):
    return 'THOUGHT:\nCheck the candidate.\nACTION:\n' + json.dumps(dict(tool_name=name, arguments=arguments))


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_notebook_syntax_and_placeholders(self):
        for c in NOTEBOOK['cells']:
            if c['cell_type'] == 'code':
                source = ''.join(c['source'])
                self.assertNotIn('********', source)
                if not source.lstrip().startswith('# Install required'):
                    compile(source, '<notebook>', 'exec')

    def test_vacation_dates(self):
        self.assertIsInstance(ns['vacation_info'].date_of_arrival, datetime.date)
        data = dict(ns['VACATION_INFO_DICT'], date_of_departure='2025-06-09')
        with self.assertRaises(ValidationError):
            ns['VacationInfo'].model_validate(data)

    def test_valid_fixture_passes_deterministic_evals(self):
        for name in ['eval_start_end_dates_match', 'eval_schedule_and_weather_match',
                     'eval_total_cost_is_accurate', 'eval_total_cost_is_within_budget',
                     'eval_itinerary_events_match_actual_events', 'eval_itinerary_satisfies_interests']:
            ns[name](ns['vacation_info'], fixture())

    def test_missing_day_and_forged_weather_fail(self):
        for mutate in [lambda p: p.itinerary_days.pop(),
                       lambda p: setattr(p.itinerary_days[2].weather, 'condition', 'clear')]:
            plan = fixture()
            mutate(plan)
            with self.assertRaises(ns['AgentError']):
                ns['eval_schedule_and_weather_match'](ns['vacation_info'], plan)

    def test_fake_activity_and_wrong_cost_fail(self):
        plan = fixture()
        plan.itinerary_days[0].activity_recommendations[0].activity.price = 0
        with self.assertRaises(ns['AgentError']):
            ns['eval_itinerary_events_match_actual_events'](ns['vacation_info'], plan)
        with self.assertRaises(ns['AgentError']):
            ns['eval_total_cost_is_accurate'](ns['vacation_info'], plan)

    def test_weather_exact_verdict(self):
        with patch.object(project_lib, 'do_chat_completion', return_value='REASONING: outdoors\nFINAL ANSWER: IS_INCOMPATIBLE'):
            with self.assertRaises(ns['AgentError']):
                ns['eval_activities_and_weather_are_compatible'](ns['vacation_info'], fixture())

    def test_feedback_count(self):
        plan = fixture()
        plan.itinerary_days[0].activity_recommendations.pop()
        with self.assertRaises(ns['AgentError']):
            ns['eval_traveler_feedback_is_incorporated'](ns['vacation_info'], plan)

    def run_agent(self, responses, result):
        agent = ns['ItineraryRevisionAgent'](system_prompt='Offline test')
        agent.get_response = lambda **kwargs: next(responses)
        fn = lambda travel_plan: result
        fn.__name__ = 'run_evals_tool'
        agent.tools = [fn, ns['final_answer_tool']]
        return agent.run_react_cycle(fixture(), max_steps=2)

    def test_passing_evaluation_allows_final(self):
        data = fixture().model_dump(mode='json')
        responses = iter([action('run_evals_tool', travel_plan=data), action('final_answer_tool', final_output=data)])
        self.assertEqual(self.run_agent(responses, {'success': True, 'failures': []}), fixture())

    def test_failed_eval_or_changed_final_cannot_exit(self):
        data = fixture().model_dump(mode='json')
        for success, change in [(False, False), (True, True)]:
            final = json.loads(json.dumps(data))
            if change:
                final['total_cost'] += 1
            responses = iter([action('run_evals_tool', travel_plan=data), action('final_answer_tool', final_output=final)])
            with self.assertRaises(RuntimeError):
                self.run_agent(responses, {'success': success, 'failures': []})

    def test_premature_final_and_malformed_action_rejected(self):
        data = fixture().model_dump(mode='json')
        responses = iter([action('final_answer_tool', final_output=data), 'THOUGHT: retry\nACTION: []'])
        with self.assertRaises(RuntimeError):
            self.run_agent(responses, {'success': True, 'failures': []})


if __name__ == '__main__':
    unittest.main()
