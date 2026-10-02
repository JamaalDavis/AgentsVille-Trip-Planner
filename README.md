# AgentsVille Trip Planner

Completed Udacity starter notebook with initial planning, Pydantic validation,
weather evaluation, tool-driven revision, and optional narration.

## Run locally

Requires Python 3.10 or newer (the provided library uses modern type syntax).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env to add your own OPENAI_API_KEY.
python -m jupyterlab project_starter.ipynb
```

Run notebook cells in order. Keys beginning with `voc` use the Vocareum endpoint;
other keys use OpenAI. `OPENAI_BASE_URL` overrides this selection. Never submit
your `.env`. The supplied GPT-4.1 family models are preserved to match the course.
API runs consume credits; narration is disabled by default.

Edit `VACATION_INFO_DICT` to change travelers, interests, dates or budget.
Mock data covers AgentsVille, June 10–15, 2025 only. Arrival and departure days
are both included. Budget means the sum of group activity prices, counted once
per event, matching the starter evaluator; lodging and flights are not modeled.

The initial planner returns JSON matching `TravelPlan`. Its prompt embeds the
schema, vacation details, weather and activity catalog. The revision prompt
lists tools dynamically and uses THOUGHT/ACTION/OBSERVATION. THOUGHT is a brief
decision summary. Python requires an initial evaluation and a successful
evaluation of the exact final candidate before allowing `final_answer_tool`.
Malformed calls become observations; exhaustion raises an explicit error.

Offline verification:

```powershell
python -m unittest -v test_project
```

Tests exercise notebook definitions with mocked model responses. They do not
establish live model quality or endpoint availability. No live API run is
included. Run the notebook with your key to assess those aspects.

API reference: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
The course's text-based ReAct protocol is retained for rubric compatibility.

Submit `project_starter.ipynb` and `project_lib.py`; include supporting README,
requirements and tests if desired. Do not include credentials.
