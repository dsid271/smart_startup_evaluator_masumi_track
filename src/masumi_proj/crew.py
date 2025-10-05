from crewai import Agent, Task, Crew, Process, LLM
import os
from crewai_tools import SerperDevTool

def create_crew():
    # Creative LLM for research/analysis steps
    gemini_llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY"),
        provider="google",
    )

    # Deterministic LLM for final evaluation / summarization
    eval_llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY"),
        provider="google",
        temperature=0.0,
    )

    # Agents
    market_researcher = Agent(
        role="Market Research Specialist",
        goal=(
            "Evaluate the market potential for the provided `startup_idea` by analyzing industry trends, "
            "demand, and target customer segments. Always use the provided `startup_idea` as-is. "
            "If details are missing, state reasonable assumptions instead of asking for clarification."
        ),
        backstory=(
            "You are an expert in market analysis, skilled at uncovering opportunities, "
            "emerging trends, and customer insights. You always preserve the `startup_idea` exactly as given."
        ),
        tools=[SerperDevTool()],
        llm=gemini_llm,
    )

    competitor_analyst = Agent(
        role="Competitor Analyst",
        goal=(
            "Identify competitors and perform a SWOT analysis for the provided `startup_idea`. "
            "Always use the exact `startup_idea` provided. If details are missing, state assumptions clearly, "
            "but do not invent or replace the idea."
        ),
        backstory=(
            "You are a strategist who understands the competitive landscape, "
            "capable of analyzing rivals and spotting differentiation opportunities."
        ),
        tools=[SerperDevTool()],
        llm=gemini_llm,
    )

    financial_forecaster = Agent(
        role="Financial Analyst",
        goal=(
            "Estimate startup costs, revenue models, and provide 1–3 year projections with break-even analysis "
            "for the provided `startup_idea`. Use the provided idea as-is. If necessary, add a note: "
            "'Some assumptions are made due to limited details.'"
        ),
        backstory=(
            "You are a financial modeling expert who transforms raw ideas into clear financial forecasts, "
            "always preserving the original `startup_idea`."
        ),
        tools=[SerperDevTool()],
        llm=gemini_llm,
    )

    pitch_deck_generator = Agent(
        role="Pitch Deck Designer",
        goal=(
            "Consolidate the research and analysis into a professional pitch deck and one-page summary "
            "for the provided `startup_idea`. Do not alter the idea. Deliver a JSON-compatible structure "
            "with a 'summary' and a 'slides' list."
        ),
        backstory=(
            "You are a creative storyteller who turns business data into compelling narratives. "
            "Your deliverable must preserve the original `startup_idea` exactly."
        ),
        tools=[SerperDevTool()],
        llm=eval_llm,
    )

    # Tasks
    market_research_task = Task(
        description=(
            "Research the market potential of the provided startup idea: {startup_idea}.\n"
            "**CRITICAL INSTRUCTION: You MUST use the exact, raw text of the startup_idea input, even if it seems incomplete or awkward. DO NOT INVENT A NEW IDEA.**\n"
            "Identify market size, growth trends, customer segments, and emerging opportunities. "
            "FINAL OUTPUT: concise market research report in JSON with keys: 'startup_idea','executive_summary','market_size','key_segments'."
            "Always include the provided startup_idea in your output exactly as given. Begin your response by restating it inside the JSON. Do not rewrite or replace it."
        ), 
        expected_output="Structured market research JSON.",
        agent=market_researcher,
    )

    competitor_analysis_task = Task(
        description=(
            "Identify direct and indirect competitors for the provided startup idea: {startup_idea}. Perform a SWOT analysis "
            "and suggest differentiators. FINAL OUTPUT: JSON with keys: 'startup_idea','competitors','swot','differentiators'."
        ),
        expected_output="Structured competitor analysis JSON.",
        agent=competitor_analyst,
    )

    financial_forecasting_task = Task(
        description=(
            "Provide financial analysis for the provided startup idea: {startup_idea}. "
            "Include assumptions, cost estimates, revenue forecasts, and break-even analysis. "
            "FINAL OUTPUT: JSON with keys: 'startup_idea','assumptions','costs','projections','break_even'."
        ),
        expected_output="Structured financial feasibility JSON.",
        agent=financial_forecaster,
    )

    pitch_deck_task = Task(
        description=(
            "Consolidate outputs from previous tasks into a professional pitch deck (5–7 slides) "
            "and a one-page summary for the provided startup idea: {startup_idea}. "
            "FINAL OUTPUT: JSON with 'summary' and 'slides' keys."
        ),
        expected_output="Pitch deck JSON with summary and slides.",
        agent=pitch_deck_generator,
    )

    # Crew
    return Crew(
        agents=[
            market_researcher,
            competitor_analyst,
            financial_forecaster,
            pitch_deck_generator,
        ],
        tasks=[
            market_research_task,
            competitor_analysis_task,
            financial_forecasting_task,
            pitch_deck_task,
        ],
        process=Process.sequential,
        verbose=True,
    )
