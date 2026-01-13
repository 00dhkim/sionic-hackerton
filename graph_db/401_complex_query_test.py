import os
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from hyde_utils import generate_hypothetical_document

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def complex_rag_test(question: str, use_hyde: bool = True):
    print(f"\n[질문]: {question}")
    
    # 1. Connect to Graph
    graph = Neo4jGraph(
        url=NEO4J_URI, 
        username=NEO4J_USER, 
        password=NEO4J_PASSWORD,
        enhanced_schema=False,
        refresh_schema=False
    )

    # 2. Vector Search (Entry Point: Complaints)
    # 우리는 민원 노드들 중에서 가장 유사한 것을 먼저 찾습니다.
    # Complaint 노드에 대한 벡터 인덱스가 필요할 수 있지만, 
    # 일단은 전체 노드 검색이 가능한 방식으로 수행하거나, 
    # 기존 Document 인덱스를 활용하되 Complaint도 검색되도록 설정해야 합니다.
    
    # 여기서는 검색의 편의를 위해 'Complaint' 노드 전용 벡터 검색을 수행합니다.
    complaint_vector = Neo4jVector.from_existing_graph(
        embedding=OpenAIEmbeddings(),
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD,
        index_name="complaint_index", # 민원용 인덱스 (없으면 자동 생성)
        node_label="Complaint",
        text_node_properties=["content"],
        embedding_node_property="embedding",
    )
    
    search_query = question
    if use_hyde:
        print(" > HyDE: 가상 문서 생성 중...")
        hypothetical_doc = generate_hypothetical_document(question)
        search_query = hypothetical_doc
        print(f"   생성된 가상 문서: {hypothetical_doc[:100]}...")
    else:
        print(" > 일반 검색 (HyDE 미사용)")
    
    print(" > 민원 데이터 검색 중...")
    relevant_complaints = complaint_vector.similarity_search(search_query, k=1)
    
    if not relevant_complaints:
        print(" > 관련 민원을 찾지 못했습니다.")
        return

    complaint = relevant_complaints[0]
    c_title = complaint.page_content[:50]
    c_idx = complaint.metadata.get('index')
    print(f" > 발견된 민원: [{c_idx}] {c_title}...")

    # 3. Graph Traversal (Expansion)
    # 민원 -> 관련 공문서 -> 작성자 -> 부서 정보를 한 번에 가져오는 쿼리
    expansion_query = """
    MATCH (c:Complaint {index: $idx})
    OPTIONAL MATCH (c)-[r:RELATED_TO]->(d:Document)
    OPTIONAL MATCH (d)<-[:AUTHORED]-(p:Person)
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(dep:Department)
    RETURN 
        c.content as complaint_content,
        d.title as doc_title,
        d.doc_id as doc_id,
        p.name as author_name,
        dep.name as dept_name,
        r.score as similarity_score
    """
    
    print(" > 그래프 경로 추적 중 (Complaint -> Document -> Person)...")
    context_data = graph.query(expansion_query, params={"idx": c_idx})
    
    if not context_data:
        print(" > 연결된 정보를 찾지 못했습니다.")
        return

    record = context_data[0]
    
    # 4. Final Context Construction
    full_context = f"""
    [민원 내용]
    {record['complaint_content']}
    
    [연결된 공문서 정보]
    - 제목: {record['doc_title']}
    - 문서번호: {record['doc_id']}
    - 유사도 점수: {record['similarity_score']}
    
    [담당자 정보]
    - 성함: {record['author_name']}
    - 소속: {record['dept_name']}
    """

    # 5. LLM 답변 생성
    template = """
    당신은 서울시 청년정책 전문가입니다. 
    제공된 [민원 내용], [공문서 정보], [담당자 정보]를 바탕으로 사용자의 질문에 답변하세요.
    반드시 연결된 공문서의 제목과 담당자 이름을 명시하여 답변의 신뢰도를 높이세요.
    
    {context}
    
    질문: {question}
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model="gpt-4o")
    chain = prompt | llm | StrOutputParser()
    
    print(" > 답변 생성 중...")
    response = chain.invoke({"context": full_context, "question": question})
    print(f"\n[최종 답변]:\n{response}")

if __name__ == "__main__":
    test_q = "청년수당 서류 미비로 인해 지급이 중단되었다는 민원이 있었는데, 이와 관련된 공문서는 무엇이고 그 문서의 작성자는 누구인지 알려줘."
    
    print("\n" + "="*60)
    print("테스트 1: HyDE 적용")
    print("="*60)
    complex_rag_test(test_q, use_hyde=True)
    
    print("\n" + "="*60)
    print("테스트 2: HyDE 미적용 (일반 검색)")
    print("="*60)
    complex_rag_test(test_q, use_hyde=False)
