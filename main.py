import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContext
from dotenv import load_dotenv
import os
from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
from datetime import datetime
import urllib.parse
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

def compile_email_body_plain(email_articles, article_links):
    body = ""
    for article, link in zip(email_articles, article_links):
        body += article + "\n"
        body += f"Read the full article here : {link}\n"
        body += "---------------------------\n"
    return body

# Configure the browser (running headless with security disabled)
browser_config = BrowserConfig(
    headless=True,
    disable_security=True,
)
browser = Browser(config=browser_config)

async def scrape_news_and_sentiment(keyword: str, max_articles: int = 5):
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))
    base_task_description = """
        1. Search Google for {keyword} and navigate to the News section.  
        2. Click on the article number {article_number} and extract its content, including the title, body, and key details.  
        3. If the article has a paywall, pop-up, or "Read More" button, bypass or extract the full content where possible.  
        4. Analyze how well the content relates to {keyword} and classify the sentiment as:
           - "Positive" → If {keyword} is the central theme.  
           - "Neutral" → If {keyword} is mentioned but not the focus.  
           - "Negative" → If the article is largely unrelated to {keyword}.  
        5. Only return a summary of the article in minimum 100 words along with the sentiment classification (Positive, Neutral, or Negative) in markdown format like ### summary: (and in next line) ### sentiment: follow this format.
    """
    results = []
    for i in range(1, max_articles + 1):
        task_description = base_task_description.format(article_number=i, keyword=keyword)
        # Disable GIF generation to avoid font issues
        agent = Agent(browser=browser, task=task_description, llm=llm, generate_gif=False)
        result = await agent.run()
        results.append(result)
    return results

# Load authentication config from YAML
with open('./config.yaml') as file:
    config_yaml = yaml.load(file, Loader=SafeLoader)
    
authenticator = stauth.Authenticate(
    config_yaml["credentials"],
    config_yaml["cookie"]["name"],
    config_yaml["cookie"]["key"],
    config_yaml["cookie"]["expiry_days"],
)

if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None

# --- Login Screen ---
if st.session_state["authentication_status"] is not True:
    st.title("🔒 Login to Access News Extractor")
    login_result = authenticator.login('main', fields={'Form name': 'Login'})
    if login_result is not None:
        name, authentication_status, username = login_result
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
    with st.sidebar:
        st.success(f"Welcome, {st.session_state.get('name', 'User')}!")
        if st.button("Logout"):
            authenticator.logout("Logout", "sidebar")
            if hasattr(authenticator, "cookie_controller"):
                authenticator.cookie_controller.delete_cookie()
            st.session_state["authentication_status"] = None
            st.rerun()
        
        st.header("Search Options")
        keyword = st.text_input("Search Keyword", value="", placeholder="Enter keyword")
        max_articles = st.slider("Number of Articles", 1, 10, 5)
        fetch_news = st.button("Fetch News", disabled=(keyword.strip() == ""))
    
    st.title("📰 AI-Powered News Extractor and Sentiment Analysis")
    st.write("Enter a keyword in the sidebar to fetch the latest news. Each article’s content will be summarized and its sentiment analyzed.")

    if fetch_news and keyword:
        with st.spinner("Agent is fetching articles for you..."):
            articles = asyncio.run(scrape_news_and_sentiment(keyword, max_articles))
        if articles:
            email_articles = []
            links = []
            allLinks = []
            for i in articles:
                email_articles.append(i.final_result())
                links = i.urls()
                allLinks.append(links[-1])
                st.markdown(i.final_result())
                with st.expander("Link to Full Article"):
                    st.write(links[-1])
                st.markdown("---")
            
            now = datetime.now()
            subject = f"Scraped News from News Extractor - {now.strftime('%Y-%m-%d %H:%M:%S')}"
            body_plain = compile_email_body_plain(email_articles,allLinks)
            encoded_subject = urllib.parse.quote(subject)
            encoded_body = urllib.parse.quote(body_plain)
            # Gmail compose URL
            gmail_link = f"https://mail.google.com/mail/?view=cm&fs=1&tf=1&su={encoded_subject}&body={encoded_body}"
            # Display the button in the sidebar as HTML
            st.sidebar.markdown(
                f'<a href="{gmail_link}" target="_blank"><button style="padding:10px; background-color:#4CAF50; border:none; color:white; font-size:16px; cursor:pointer;">Send News via Gmail</button></a>',
                unsafe_allow_html=True
            )
            
        else:
            st.error("No articles found. Try a different keyword.")
