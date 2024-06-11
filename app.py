import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urlparse, urljoin
import smtplib
from email.mime.text import MIMEText

# Initialize OpenAI API key
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""

# Initialize SMTP configurations
if "smtp_configs" not in st.session_state:
    st.session_state.smtp_configs = []

# Initialize domain data
if "domain_data" not in st.session_state:
    st.session_state.domain_data = []

# Initialize user information
if "user_info" not in st.session_state:
    st.session_state.user_info = {
        "name": "",
        "business_name": "",
        "website": "",
        "business_description": "",
        "email": "",
        "phone_number": ""
    }

def show_settings():
    st.sidebar.title("Settings")

    st.sidebar.subheader("OpenAI API Key")
    openai_api_key = st.sidebar.text_input("Enter your OpenAI API key", type="password", value=st.session_state.openai_api_key)
    st.session_state.openai_api_key = openai_api_key

    st.sidebar.subheader("SMTP Configuration")
    smtp_configs = st.sidebar.text_area("Enter SMTP configurations (one per line, format: smtp_server,smtp_port,email,password)", value="\n".join([f"{config['smtp_server']},{config['smtp_port']},{config['email']},{config['password']}" for config in st.session_state.smtp_configs]))
    st.session_state.smtp_configs = [
        {
            "smtp_server": config.split(",")[0],
            "smtp_port": int(config.split(",")[1]),
            "email": config.split(",")[2],
            "password": config.split(",")[3]
        }
        for config in smtp_configs.split("\n") if config.strip()
    ]

    st.sidebar.subheader("User Information")
    st.session_state.user_info["name"] = st.sidebar.text_input("Name", value=st.session_state.user_info["name"])
    st.session_state.user_info["business_name"] = st.sidebar.text_input("Business Name", value=st.session_state.user_info["business_name"])
    st.session_state.user_info["website"] = st.sidebar.text_input("Website", value=st.session_state.user_info["website"])
    st.session_state.user_info["business_description"] = st.sidebar.text_area("Business Description", value=st.session_state.user_info["business_description"])
    st.session_state.user_info["email"] = st.sidebar.text_input("Email", value=st.session_state.user_info["email"])
    st.session_state.user_info["phone_number"] = st.sidebar.text_input("Phone Number", value=st.session_state.user_info["phone_number"])

st.set_page_config(page_title="Domain Scraper", page_icon="🌐", layout="wide")
st.markdown("""
<style>
.css-18e3th9 {
    padding-top: 1rem;
    padding-bottom: 10rem;
    background-color: #e6f2ff;
}
</style>
""", unsafe_allow_html=True)

show_settings()

st.title("🔍 Domain Scraper with Email Extraction and Personalized Outreach")

domains = st.text_area("Enter domains (one per line)")

def scrape_domains(domains):
    domain_data = []
    for domain in domains.split("\n"):
        try:
            parsed_url = urlparse(domain)
            if not parsed_url.scheme:
                url = f"https://{domain}"
            else:
                url = domain

            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for non-2xx status codes
            soup = BeautifulSoup(response.text, "html.parser")

            domain_name = parsed_url.netloc

            # Handle cases where elements are not found
            title_element = soup.find("title")
            if title_element:
                page_title = title_element.get_text()
            else:
                page_title = ""

            meta_description_element = soup.find("meta", attrs={"name":"description"})
            if meta_description_element:
                meta_description = meta_description_element.get("content", "")
            else:
                meta_description = ""

            main_text = " ".join([p.get_text() for p in soup.find_all("p")])

            # Extract email addresses using multiple methods
            emails = set()

            # Method 1: Regular expression on HTML content
            emails.update(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", response.text))

            # Method 2: mailto: links
            mailto_links = soup.find_all("a", href=re.compile(r"mailto:"))
            emails.update([link.get("href").replace("mailto:", "") for link in mailto_links])

            # Method 3: Text content of HTML elements
            for element in soup.find_all(string=re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), recursive=True):
                emails.add(element)

            # Method 4: HTML attributes
            for tag in soup.find_all(True):
                for attr in tag.attrs.values():
                    emails.update(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", str(attr)))

            # Method 5: Find "Contact Us" page and extract emails
            contact_links = soup.find_all("a", string=re.compile(r"Contact( Us)?", re.IGNORECASE))
            for link in contact_links:
                contact_url = urljoin(url, link.get("href"))
                try:
                    contact_response = requests.get(contact_url)
                    contact_response.raise_for_status()
                    contact_soup = BeautifulSoup(contact_response.text, "html.parser")
                    emails.update(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", contact_soup.get_text()))
                except Exception as e:
                    st.warning(f"⚠️ Error retrieving contact page for {domain_name}: {e}")

            # Convert the set to a list
            emails = list(emails)

            # Generate personalized outreach using OpenAI API
            prompt = f"Based on the following information about the website {domain_name}:\n\nTitle: {page_title}\nDescription: {meta_description}\nMain Text: {main_text[:500]}...\n\nCraft a personalized email outreach for a backlink opportunity. The email should be friendly, engaging, and highlight the relevance of the website's content to our business. Keep the email concise and actionable.\n\nAdditionally, please include a signature with the following details:\n\nName: {st.session_state.user_info['name']}\nBusiness Name: {st.session_state.user_info['business_name']}\nWebsite: {st.session_state.user_info['website']}\nBusiness Description: {st.session_state.user_info['business_description']}\nEmail: {st.session_state.user_info['email']}\nPhone Number: {st.session_state.user_info['phone_number']}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {st.session_state.openai_api_key}"
            }
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "n": 1,
                "stop": None,
                "temperature": 0.7
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            outreach_email = response.json()["choices"][0]["message"]["content"].strip()

            # Ask OpenAI to suggest the best email for outreach
            email_prompt = f"Here are the email addresses found on the website {domain_name}:\n\n{', '.join(emails)}\n\nBased on the website content and the personalized outreach email, which email address would be the most appropriate to send the outreach to? Please make sure to only respond with the suggested email, nothing else!"
            email_data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": email_prompt}, {"role": "assistant", "content": outreach_email}],
                "max_tokens": 100,
                "n": 1,
                "stop": None,
                "temperature": 0.7
            }
            email_response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=email_data)
            email_response.raise_for_status()
            suggested_email = email_response.json()["choices"][0]["message"]["content"].strip()

            domain_data.append({
                "domain": domain_name,
                "outreach_email": outreach_email,
                "suggested_email": suggested_email
            })
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Error scraping data for {domain}: {e}")
            logging.error(f"Error scraping {domain}: {e}")
        except Exception as e:
            st.error(f"❌ Error scraping data for {domain}: {e}")
            logging.error(f"Error scraping {domain}: {e}")

    return domain_data

def show_domain_data():
    if st.session_state.domain_data:
        st.subheader("Domain Data")
        for data in st.session_state.domain_data:
            st.write(f"**Domain:** {data['domain']}")
            st.write(f"**Personalized Outreach Email:**")
            st.write(data["outreach_email"])
            st.write(f"**Suggested Email:** {data['suggested_email']}")
            st.write("---")
    else:
        st.warning("No domain data available. Please scrape domains first.")

def send_outreach_email(domain_data, outreach_subject, outreach_email, selected_email):
    if not st.session_state.smtp_configs:
        st.warning("Please configure SMTP settings in the sidebar.")
        return

    for data in domain_data:
        if selected_email == data["suggested_email"]:
            msg = MIMEText(outreach_email)
            msg["Subject"] = outreach_subject
            msg["From"] = st.session_state.smtp_configs[0]["email"]
            msg["To"] = selected_email

            try:
                with smtplib.SMTP(st.session_state.smtp_configs[0]["smtp_server"], st.session_state.smtp_configs[0]["smtp_port"]) as smtp:
                    smtp.starttls()
                    smtp.login(st.session_state.smtp_configs[0]["email"], st.session_state.smtp_configs[0]["password"])
                    smtp.send_message(msg)
                st.success(f"Email sent successfully to {selected_email} for {data['domain']}")
            except Exception as e:
                st.error(f"Error sending email to {selected_email} for {data['domain']}: {e}")

if st.button("Scrape Domains"):
    st.session_state.domain_data = scrape_domains(domains)
    show_domain_data()

show_domain_data()

outreach_subject = st.text_input("Outreach Email Subject")
outreach_email = st.text_area("Outreach Email Content")
selected_email = st.selectbox("Select Email for Outreach", [data["suggested_email"] for data in st.session_state.domain_data])

if st.button("Send Outreach Email"):
    send_outreach_email(st.session_state.domain_data, outreach_subject, outreach_email, selected_email)
