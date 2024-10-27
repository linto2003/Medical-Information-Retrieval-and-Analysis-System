from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
import streamlit as st
from neo4j import GraphDatabase
from ctransformers import AutoModelForCausalLM
from langchain_community.llms import CTransformers
from langchain_mistralai import ChatMistralAI
import getpass
import os

class Neo4jGraphHandler:
    def __init__(self, url, username, password):
        self._driver = GraphDatabase.driver(url, auth=(username, password))
        self._database = "neo4j"

    def close(self):
        self._driver.close()

    def run(self, query):
        with self._driver.session() as session:
            return session.run(query)


def main():
    st.set_page_config(
        layout="wide",
        page_title="Graphy - Talk to Graphs",
        page_icon=":graph:"
    )
    st.sidebar.image('logo.jpg', use_column_width=True)
    
    with st.sidebar.expander("Expand Me"):
        st.markdown("""
    This application allows you to generate Cypher queries that interact with the Neo4j database in real-time.
    """)
    
    st.title("Graphy - Talk to Graphs")

    # Initialize HuggingFace embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Connect to Neo4j Graph
    graph_handler = Neo4jGraphHandler(
        url="neo4j+s://38a7aab1.databases.neo4j.io:7687",
        username=os.environ.get('NEO4J_USER_NAME'),
        password=os.environ.get('NEO4J_PASSWORD')
    )
    
    graph = Neo4jGraph(
        url="neo4j+s://38a7aab1.databases.neo4j.io:7687",
        username=os.environ.get('NEO4J_USER_NAME'),
        password=os.environ.get('NEO4J_PASSWORD'),
        database="neo4j"
    )

  
    index_name = "medicine_embeddings"
    text_node_properties = ["name"]

    index = Neo4jVector.from_existing_graph(
        embedding=embeddings,
        graph=graph,
        database="neo4j",
        node_label="Medicine",  
        text_node_properties=text_node_properties,  
        embedding_node_property="embedding",
        index_name=index_name,  
        keyword_index_name=index_name,  

    )

    # Get schema from graph
    schema = graph.get_schema

    # Create PromptTemplate for Cypher query generation
    template = """
    Task: Generate a Cypher statement to query which is not case sensitive the graph database in Neo4j.

    Instructions:
    Use only relationship types and properties provided in the schema.
    Do not use other relationship types or properties that are not provided.

    schema:
    {schema}

    Note: Do not include explanations or apologies in your answers.
    Do not answer questions that ask anything other than creating Cypher statements.
    Do not include any text other than generated Cypher statements.

    Question: {question}
    """
    
    question_prompt = PromptTemplate(
        template=template,
        input_variables=["schema", "question"]
    )
    

    llm = ChatMistralAI(model="mistral-large-latest",temparature=0)

    # Set up the QA chain using the LLM and graph
    qa = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=question_prompt,
        verbose=True,
        allow_dangerous_queries=True,
        allow_dangerous_requests =True
    )
    
    # Store the QA chain in session state
    st.session_state['qa'] = qa
    
   
    if 'qa' in st.session_state:
        st.subheader("Ask a Question")
        with st.form(key='question_form'):
            question = st.text_input("Enter your question:")
           
            submit_button = st.form_submit_button(label='Submit')
        try:
            if submit_button and question:
                with st.spinner("Generating answer..."):
                    res = st.session_state['qa']({"query": question})
                    st.write("\n**Answer:**\n" + res['result'])
        except Exception as e:
            st.write(e)

if __name__ == "__main__":
    main()
