"""
Offline Documentation Analyzer
Utilizes a local Ollama LLM to parse and analyze the project's README.md file
for architectural review and automated documentation insights.
"""
import os
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate

# Default to qwen2.5-coder:1.5b, can be overridden by environment variable
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")

def analyze_readme():
    print(f"[*] Initializing local Ollama model ({OLLAMA_MODEL})...")
    try:
        llm = Ollama(model=OLLAMA_MODEL)
    except Exception as e:
        print(f"[!] Failed to initialize Ollama: {e}")
        return

    readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'README.md')
    
    if not os.path.exists(readme_path):
        print(f"[!] Target file not found at {readme_path}")
        return

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
    except Exception as e:
        print(f"[!] Error reading file: {e}")
        return
        
    # Check if there are any live changes made by the evaluator using git diff
    import subprocess
    diff_output = ""
    try:
        diff_proc = subprocess.run(["git", "diff", "README.md"], capture_output=True, text=True, cwd=os.path.dirname(readme_path))
        diff_output = diff_proc.stdout
    except Exception:
        pass

    if diff_output.strip():
        print("[*] Detected live uncommitted changes! Analyzing the exact changes...")
        prompt_text = """You are a technical documentation analyzer. An evaluator just made changes to the project's README.md file.
        Here is the exact DIFF of their changes:
        {diff}
        
        Please analyze EXACTLY what they changed, added, or removed. If they introduced errors or typos, point them out. Present a clear analysis of the modifications.
        
        ANALYSIS:"""
        prompt = PromptTemplate.from_template(prompt_text)
        chain = prompt | llm
        chain_args = {"diff": diff_output}
    else:
        # Fallback to analyzing the whole document if no live changes are detected
        prompt_text = """You are a technical documentation analyzer. Please review the following project README.
        Identify the core architecture, key concepts, and structural highlights.
        Present your findings in a clear, professional summary.

        DOCUMENT CONTENTS:
        {readme_text}

        ANALYSIS:"""
        prompt = PromptTemplate.from_template(prompt_text)
        chain = prompt | llm
        chain_args = {"readme_text": readme_content}
    
    print("[*] Analyzing documentation using offline model... (this may take a moment)")
    
    try:
        result = chain.invoke(chain_args)
    except Exception as e:
        print(f"[!] Analysis failed. Ensure Ollama is running locally. Error: {e}")
        return
        
    output_path = os.path.join(os.path.dirname(__file__), "DOCUMENTATION_ANALYSIS.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Documentation Analysis Report\n\n")
        f.write(result)
        
    print("\n" + "="*50)
    print(f"[+] Analysis Complete. Report saved to: {output_path}")
    print("="*50)
    print(result)

if __name__ == "__main__":
    analyze_readme()
