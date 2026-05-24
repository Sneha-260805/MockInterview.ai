import os
import google.generativeai as genai

def check_gemini_key():
    api_key = os.getenv("gemini_api_key")
    if not api_key:
        raise SystemExit("Set gemini_api_key in your environment before running.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content("Hello, please reply with a short test message.")
    
    print("Status: OK")
    print("Response:")
    print(response.text)

if __name__ == "__main__":
    check_gemini_key()