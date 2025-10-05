from masumi_proj.crew import create_crew
from dotenv import load_dotenv
import json
load_dotenv()

def get_startup_idea():
    while True:
        idea = input("Enter your startup idea (or type 'generate' to let the crew propose one): ").strip()
        if not idea or idea.lower() in ("no idea", "none", "n/a"):
            confirm = input("No idea entered. Do you want the crew to generate an idea? (y/N): ").strip().lower()
            if confirm == "y":
                return None  # signal: let crew generate
            print("Please enter a short idea or type 'generate'.")
            continue
        if idea.lower() == "generate":
            return None
        return idea

# helper: robust extraction that handles crew Output.json() raising ValueError
def extract_result_text(result):
    # try common attributes first
    for attr in ("final_output", "output", "text"):
        val = getattr(result, attr, None)
        if val is not None:
            return val
    # crew.Output.json() may raise ValueError when no JSON was produced
    try:
        if hasattr(result, "json"):
            j = result.json()
            if j:
                return j
    except ValueError:
        # explicit: no JSON present, ignore
        pass
    except Exception:
        pass
    # try dict() if available
    try:
        if hasattr(result, "dict"):
            d = result.dict()
            if d:
                # prefer a common key if present
                for key in ("startup_idea", "idea", "generated_idea", "final_output"):
                    if isinstance(d, dict) and key in d:
                        return d[key]
                return d
    except Exception:
        pass
    # fallback to string
    try:
        return str(result)
    except Exception:
        return "<unserializable result>"

def run():
    print("🚀 Startup Idea Evaluator Crew")
    startup_idea = get_startup_idea()

    crew = create_crew()

    # If user asked generation, run a generation step and require confirmation
    if startup_idea is None:
        while True:
            gen_result = crew.kickoff(inputs={"startup_idea": None, "stage": "generate"})
            gen = extract_result_text(gen_result)
            print("\nGenerated idea:\n", gen)
            accept = input("Accept this idea? (Y/n): ").strip().lower()
            if accept in ("", "y", "yes"):
                # ensure a plain string
                startup_idea = gen if isinstance(gen, str) else str(gen)
                break
            retry = input("Generate another? (Y/n): ").strip().lower()
            if retry in ("n", "no"):
                startup_idea = get_startup_idea()
                break

    # Final evaluation step: lock the idea and force evaluate stage
    final_result = crew.kickoff(inputs={"startup_idea": startup_idea})

    print("\n=== Final Evaluation ===\n")
    print(final_result)

    final = extract_result_text(final_result)

    # write output
    with open("output.txt", "w", encoding="utf-8") as f:
        if isinstance(final, (dict, list)):
            f.write(json.dumps(final, ensure_ascii=False, indent=2))
        else:
            f.write(str(final))

if __name__ == "__main__":
    run()
