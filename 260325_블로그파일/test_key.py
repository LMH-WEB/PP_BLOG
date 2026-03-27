import google.generativeai as genai

api_key = input("Gemini API 키를 입력하세요: ").strip()

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content("안녕하세요. 테스트입니다.")
    print("\n✅ API 키 정상 작동!")
    print("응답:", response.text[:100])
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
