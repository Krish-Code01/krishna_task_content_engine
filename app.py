import streamlit as st
from langchain.chains import ConversationalRetrievalChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.llms import LlamaCpp
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import tempfile
import multiprocessing
from multiprocessing import Pool


# Function to process PDF files and extract text
def process_pdf_files(uploaded_files):
    text = []
    for file in uploaded_files:
        file_extension = os.path.splitext(file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file.read())
            temp_file_path = temp_file.name
        loader = None
        if file_extension == ".pdf":
            loader = PyPDFLoader(temp_file_path)
        if loader:
            text.extend(loader.load())
            os.remove(temp_file_path)
    return text

# Function to initialize session state variables
def initialize_session_state():
    if 'history' not in st.session_state:
        st.session_state['history'] = []
    if 'generated' not in st.session_state:
        st.session_state['generated'] = ["Hello! Ask me anything about 🤗"]
    if 'past' not in st.session_state:
        st.session_state['past'] = ["Hey! 👋"]

# Function to handle conversation with the LlamaCpp model
def conversation_chat(query, chain, history):
    result = chain.invoke({"question": query, "chat_history": history})
    history.append((query, result["answer"]))
    return result["answer"]

# Function to display chat history in the Streamlit UI
def display_chat_history(chain):
    reply_container = st.container()
    container = st.container()
    with container:
        with st.form(key='my_form', clear_on_submit=True):
            user_input = st.text_input("Question:", placeholder="Ask about your PDF", key='input')
            submit_button = st.form_submit_button(label='Send')
        if submit_button and user_input:
            with st.spinner('Generating response...'):
                output = conversation_chat(user_input, chain, st.session_state['history'])
            st.session_state['past'].append(user_input)
            st.session_state['generated'].append(output)
    if st.session_state['generated']:
        with reply_container:
            for i in range(len(st.session_state['generated'])):
                st.markdown(f'<span style="font-size: 2em;">😎</span>: {st.session_state["past"][i]}', unsafe_allow_html=True)
                st.markdown(f'<span style="font-size: 2em;">🤖</span>: {st.session_state["generated"][i]}', unsafe_allow_html=True)
                st.markdown("---")

# Function to create the conversational chain
def create_conversational_chain(text_chunks):
    llm = LlamaCpp(
        streaming=True,
        model_path="models/mistral-7b-instruct-v0.1.Q4_K_S.gguf",
        temperature=0.75,
        top_p=1,
        verbose=True,
        n_ctx=4096,
        n_gpu_layers=-1, 
        n_batch=512 
    )
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'} 
    )
    vector_store = FAISS.from_documents(text_chunks, embedding=embeddings)
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        chain_type='stuff',
        retriever=vector_store.as_retriever(search_kwargs={"k": 2}),
        memory=memory
    )
    return chain



# Main function to run the Streamlit app
def main():
    initialize_session_state()
    st.title("Almeno Chatbot")
    st.sidebar.title("Document Processing")
    uploaded_files = st.sidebar.file_uploader("Upload files", accept_multiple_files=True)

    if uploaded_files:
        with st.spinner("Processing the files..."):
            with Pool() as pool:
                text_chunks = pool.map(process_pdf_files, [uploaded_files])[0]
        chain = create_conversational_chain(text_chunks)
        display_chat_history(chain)


if __name__ == '__main__':
    main()