import requests
import json
from typing import Dict, List
from hyde_utils import generate_hypothetical_document

API_URL = "http://localhost:8000/api/search"

test_questions = [
    "청년수당 서류 미비로 인해 지급이 중단되었다는 민원이 있었는데, 이와 관련된 공문서는 무엇이고 그 문서의 작성자는 누구인지 알려줘.",
    "청년수당 신청 자격은 무엇인가요?",
    "청년수당 지급 조건에 대해 알려주세요.",
    "서류 미비 시 어떻게 해야 하나요?",
    "청년수당 이의신청 절차는 어떻게 되나요?",
]


def test_hyde_on_questions(questions: List[str]) -> Dict:
    """
    여러 질문에 대해 HyDE와 일반 검색의 결과를 비교합니다.
    """
    results = {
        "standard": [],
        "hyde": [],
        "comparisons": []
    }
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"질문 {i}/{len(questions)}: {question}")
        print('='*60)
        
        # Standard Search
        print("\n[일반 검색 결과]")
        try:
            std_response = requests.post(
                API_URL, 
                json={"query": question, "use_hyde": False},
                timeout=30
            )
            std_data = std_response.json()
            std_sources = [s["title"] for s in std_data.get("sources", [])]
            print(f"찾은 문서 수: {len(std_sources)}")
            for j, src in enumerate(std_sources, 1):
                print(f"  {j}. {src[:60]}...")
            
            results["standard"].append({
                "question": question,
                "sources": std_sources,
                "answer_length": len(std_data.get("answer", ""))
            })
        except Exception as e:
            print(f"에러: {e}")
            results["standard"].append({"question": question, "error": str(e)})
        
        # HyDE Search
        print("\n[HyDE 검색 결과]")
        print("가상 문서 생성 중...")
        try:
            hyde_response = requests.post(
                API_URL,
                json={"query": question, "use_hyde": True},
                timeout=30
            )
            hyde_data = hyde_response.json()
            hyde_sources = [s["title"] for s in hyde_data.get("sources", [])]
            hypothetical_doc = hyde_data.get("hypothetical_document", "")
            print(f"가상 문서: {hypothetical_doc[:100]}...")
            print(f"찾은 문서 수: {len(hyde_sources)}")
            for j, src in enumerate(hyde_sources, 1):
                print(f"  {j}. {src[:60]}...")
            
            results["hyde"].append({
                "question": question,
                "sources": hyde_sources,
                "answer_length": len(hyde_data.get("answer", "")),
                "hypothetical_doc": hypothetical_doc
            })
            
            # Compare results
            comparison = {
                "question": question,
                "standard_count": len(std_sources),
                "hyde_count": len(hyde_sources),
                "overlap": len(set(std_sources) & set(hyde_sources)),
                "hyde_unique": list(set(hyde_sources) - set(std_sources)),
                "std_unique": list(set(std_sources) - set(hyde_sources))
            }
            results["comparisons"].append(comparison)
            
            print("\n[비교]")
            print(f"일반 검색 문서: {comparison['standard_count']}")
            print(f"HyDE 검색 문서: {comparison['hyde_count']}")
            print(f"중복 문서: {comparison['overlap']}")
            if comparison['hyde_unique']:
                print(f"HyDE만 찾은 문서: {comparison['hyde_unique'][0][:50]}...")
            
        except Exception as e:
            print(f"에러: {e}")
            results["hyde"].append({"question": question, "error": str(e)})
    
    return results


def print_summary(results: Dict):
    """
    테스트 결과 요약을 출력합니다.
    """
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)
    
    total_questions = len(results["comparisons"])
    hyde_better = sum(1 for c in results["comparisons"] if c["hyde_count"] > c["standard_count"])
    std_better = sum(1 for c in results["comparisons"] if c["standard_count"] > c["hyde_count"])
    equal = sum(1 for c in results["comparisons"] if c["hyde_count"] == c["standard_count"])
    
    print(f"총 질문 수: {total_questions}")
    print(f"HyDE가 더 많은 문서를 찾은 경우: {hyde_better}")
    print(f"일반 검색이 더 많은 문서를 찾은 경우: {std_better}")
    print(f"동일한 결과: {equal}")
    
    avg_std = sum(r.get("answer_length", 0) for r in results["standard"]) / total_questions if total_questions > 0 else 0
    avg_hyde = sum(r.get("answer_length", 0) for r in results["hyde"]) / total_questions if total_questions > 0 else 0
    
    print(f"\n평균 답변 길이:")
    print(f"  일반 검색: {avg_std:.0f} 자")
    print(f"  HyDE: {avg_hyde:.0f} 자")


if __name__ == "__main__":
    print("HyDE 성능 테스트 시작...")
    print(f"API 서버가 {API_URL}에서 실행 중이어야 합니다.")
    
    try:
        results = test_hyde_on_questions(test_questions)
        print_summary(results)
        
        # Save results to file
        with open("hyde_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("\n결과가 hyde_test_results.json에 저장되었습니다.")
        
    except requests.exceptions.ConnectionError:
        print("오류: API 서버에 연결할 수 없습니다.")
        print(f"API 서버가 {API_URL}에서 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
