from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(model="gpt-4o")

hyde_prompt = ChatPromptTemplate.from_template(
    """
    당신은 서울시 청년정책 전문가입니다.
    사용자의 질문에 대해 자연스럽고 상세한 답변을 작성해주세요.
    정책 내용, 절차, 담당자 정보 등을 포함하여 구체적으로 작성하세요.
    실제 공문서나 민원 답변의 스타일이 아니라, 이해하기 쉬운 자연스러운 한국어 답변을 작성하세요.
    
    질문: {question}
    
    답변:
    """
)

hyde_chain = hyde_prompt | llm | StrOutputParser()


def generate_hypothetical_document(question: str) -> str:
    """
    HyDE(Hypothetical Document Embeddings) 기법을 적용하여
    질문으로부터 가상 문서를 생성합니다.
    
    Args:
        question: 사용자 질문
        
    Returns:
        생성된 가상 문서
    """
    return hyde_chain.invoke({"question": question})
