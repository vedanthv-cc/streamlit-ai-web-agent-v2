import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from browser_use import Agent, Browser
from browser_use.browser.context import BrowserContext
from dotenv import load_dotenv
import os
from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
browser = Browser()

async def scrape_news_and_sentiment(keyword: str, max_articles: int = 5):
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))
    base_task_description = """
        1. Search Google for {keyword} and navigate to the News section.  
        2. Click on the artical number {article_number} and extract its content, including the title, body, and key details.  
        3. If the article has a paywall, pop-up, or "Read More" button, bypass or extract the full content where possible.  
        4. Analyze how well the content relates to {keyword} and classify the sentiment as:
        - "Positive" → If {keyword} is the central theme.  
        - "Neutral" → If {keyword} is mentioned but not the focus.  
        - "Negative" → If the article is largely unrelated to {keyword}.  
        5. Only Return a summary of the article along with the sentiment classification (Positive, Neutral, or Negative).  
    """
    results = []
    for i in range(1, max_articles + 1):
        task_description = base_task_description.format(article_number=i, keyword=keyword)

        agent = Agent(task=task_description, llm=llm)

        result = await agent.run()
        results.append(result)
    return results

with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)
    
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None

# --- Login Screen ---
if st.session_state["authentication_status"] is not True:
    st.title("🔒 Login to Access News Extractor")
    name, authentication_status, username = authenticator.login('main', fields={'Form name': 'Login'})
    if authentication_status:
        st.session_state["authentication_status"] = True
        st.session_state["name"] = name
        st.session_state["username"] = username
    elif authentication_status is False:
        st.error("Username or password is incorrect")
    else:
        st.warning("Please enter your credentials to continue.")
    if st.session_state["authentication_status"] is not True:
        st.stop()

# --- Main App (After Authentication) ---
if st.session_state["authentication_status"]:
    # Sidebar: Logout and search options are all inside one container
    with st.sidebar:
        st.success(f"Welcome, {st.session_state.get('name', 'User')}!")
        if st.button("Logout"):
            authenticator.logout("Logout", "sidebar")
            if hasattr(authenticator, "cookie_controller"):
                authenticator.cookie_controller.delete_cookie()
            st.session_state["authentication_status"] = None
        
        st.header("Search Options")
        keyword = st.text_input("Search Keyword", value="", placeholder="Enter keyword")
        max_articles = st.slider("Number of Articles", 1, 10, 5)
        fetch_news = st.button("Fetch News", disabled=(keyword.strip() == ""))

    st.title("📰 AI-Powered News Extractor and Sentiment Analysis")
    st.write("Enter a keyword in the sidebar to fetch the latest news. Each article’s content will be summarized and its sentiment analyzed.")

    # Fetch and display articles when the "Fetch News" button is clicked
    if fetch_news and keyword:
        with st.spinner("Fetching articles..."):
            articles = asyncio.run(scrape_news_and_sentiment(keyword, max_articles))
        if articles:
            for idx, article in enumerate(articles, start=1):
                st.markdown(f"### Article {idx}")
                st.write(article)
                st.markdown("---")
        else:
            st.error("No articles found. Try a different keyword.")
