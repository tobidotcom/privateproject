import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urlparse, urljoin
import smtplib
from email.mime.text import MIMEText
import random

# Initialize session state variables
st.session_state.setdefault('openai_api_key', "")
st.session_state.setdefault('smtp_configs', [])
st.session_state.setdefault('domain_data', [])
st.session_state.setdefault('user_info', {
    "name": "", "business_name": "", "website": "", "business_description": "", "email": "", "phone_number": ""})
st.session_state.setdefault('emails_sent', {})
st.session_state.setdefault('proxies', [])

def show_settings():
    st.sidebar.title("Settings")
    openai_api_key = st.sidebar.text_input("OpenAI API Key", st.session_state.openai_api_key, type="password", key="openai_api_key")
    if openai_api_key != st.session_state.openai_api_key:
        st.session_state.openai_api_key = openai_api_key

    st.sidebar.subheader("User Information")
    for key, label in st.session_state.user_info.items():
        placeholder = {
            "name": "John Doe",
            "business_name": "Acme Inc.",
            "website": "https://example.com",
            "business_description": "We provide top-notch software solutions.",
            "email": "john@example.com",
            "phone_number": "+1 (555) 123-4567"
        }.get(key, "")
        st.session_state.user_info[key] = st.sidebar.text_input(label, st.session_stateuser_info[key], placeholder=placeholder, key=f"user_info_{key}")

    st.sidebar.subheader("SMTP Configurations")
    smtp_configs = st.session_state.smtp_configs.copy()
    for i, config in enumerate(smtp_configs):
        with st.sidebar.expander(f"Configuration {i+1}"):
            for key in config:
                config[key] = st.text_input(f"{key.capitalize()} {i+1}", config[key], type="password" if key == "password" else "default", key=f"smtp_config_{i}_{key}")

            if st.button(f"Check Configuration {i+1}", key=f"check_config_{i}"):
                try:
                    smtp = smtplib.SMTP_SSL(config["server"], config["port"]) if config["port"] == 465 else smtplib.SMTP(config["server"], config["port"])
                    smtp.starttls() if config["port"] != 465 else None
                    smtp.login(config["username"], config["password"])
                    smtp.quit()
                    st.success(f"Configuration {i+1} is valid.")
                except smtplibSMTPAuthenticationError:
                    st.error(f"Authentication failed for Configuration {i+1}.")
                except Exception as e:
                    st.error(f"Error checking Configuration {i+1}: {e}")

    st.session_state.smtp_configs = smtp_configs
    if st.sidebar.button("Add SMTP Configuration", key="add_smtp_config"):
        st.session_state.smtp_configs.append({"server": "", "port": 587, "username": "", "password": "", "sender_email": ""})

    st.sidebar.subheader("Proxy Configurations")
    proxies = st.session_state.proxies.copy()
    for i, proxy in enumerate(proxies):
        with st.sidebar.expander(f"1}"):
            proxy = st.text_input(f"Proxy {i+1}", proxy, key=f"proxy_{i}")
            proxies[i] = proxy

    st.session_state.proxies = proxies
    if st.sidebar.button("Add Proxy", key="add_proxy"):
        st.session_state.proxies.append("")

st.set_page_config(page_title="Domain Scraper", layout="wide")
show_settings()
st.title("Domain Scraper with Email Extraction and Personalized Outreach")
keywords = st.text_input("Enter keywords for SERP scraping")

def scrape_serps(keywords):
    domain_list = []
    try:
        url = f"https://www.google.com/search?q={keywords}"
        response = requests.get(url, proxies=get_proxy())
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a"):
            href = link.get("href")
            if href and "url?q=" in href:
                domain = urlparse(href).netloc
                if domain not in domain_list:
                    domain_list.append(domain)
    except requests.exceptions.RequestException as e:
        st.error(f"Error scraping SERPs for {keywords}: {e}")
        logging.error(f"Error scraping SERPs for {keywords}: {e}")
    except Exception as e:
        st.error(f"Error scraping SERPs for {keywords}: {e}")
        logging.error(f"Error scraping SERPs for {keywords}: {e}")
    return domain_list

def get_proxy():
    if st.session_state.proxies:
        return {"http": random.choice(st.session_state.proxies), "https": random.choice(st.session_state.proxies)}
    return None

def scrape_domains(domains):
    domain_data = []
    for domain in domains:
        try:
            url = f"https://{domain}" if not urlparse(domain).scheme else domain
            response = requests.get(url, proxies=get_proxy())
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            domain_name = urlparse(url).netloc
            page_title = soup.find("title")
            page_title = page_title.get_text() if page_title else ""
            meta_description = soup.find("meta", attrs={"name": "description"})
            meta_description = meta_description.get("content", "") if meta_description else ""
            main_text = " ".join([p.get_text() for p in soup.find_all("p")])

            emails =(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", response.text))
            emails.update([link.get("href").replace("mailto:", "") for link in soup.find_all("a", href=re.compile(r"mailto:"))])
            for element in soup.find_all(text=re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), recursive=True):
                emails.add(element)
            for tag in soup.find_all(True):
                for attr in tag.attrs.values():
                    emails.update(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", str(attr)))
            for link in soup.find_all("a", string=re.compile(r"Contact( Us)?", re.IGNORECASE)):
                try:
                    contact_soup = BeautifulSoup(requests.get(urljoin(url, link.get("href")), proxies=get_proxy()).text, "html.parser")
                    emails.update(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", contact_soup.get_text()))
                except Exception as e:
                    st.warning(f"Error retrieving contact page for {domain_name}: {e}")

            prompt = f"""
            Based on the following information about the website {domain_name}:
            Title: {page_title}
            Description: {meta_description}
            Main Text: {main_text[:500]}...
            Craft a personalized email outreach for a backlink opportunity.
            The email should be friendly, engaging, and highlight the relevance of the website's content to our business.
            Keep the email concise and actionable.
            Additionally, please include a signature with the following details:
            Name: {st.session_state.user_info['name']}
            Business Name: {st.session_state.user_info['business_name']}
            Website: {st.session_state.user_info['website']}
            Business Description: {st.session_state.user_info['business_description']}
            Email: {st.session_state.user_info['email']}
            Phone Number: {st.session_state.user_info['phone_number']}
            """
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {st.session_state.openai_api_key}"}
            data = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "max_tokens": 500, "n": 1, "stop": None, "temperature": 0.7}
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            outreach_email = response.json()["choices"][0]["message"]["content"].strip()

            email_prompt = f"Here are the email addresses found on the website {domain_name}:\n\n{', '.join(emails)}\n\nBased on the website content and the personalized outreach email, which email address would be the most appropriate to send the outreach to? Please make sure to only respond with the suggested email, nothing else!"
            email_data = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": email_prompt}, {"role": "assistant", "content": outreach_email}], "max_00, "n": 1, "stop": None, "temperature": 0.7}
            email_response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=email_data)
            email_response.raise_for_status()
            suggested_email = email_response.json()["choices[0]["message"]["content"].strip()

            domain_data.append({"domain": domain_name, "outreach_email": outreach_email, "suggested_email": suggested_email})
        except requests.exceptions.RequestException as e:
            st.error(f"Error scraping data for {domain}: {e}")
            logging.error(f"Error scraping {domain}: {e}")
        except Exception as e:
            st.error(f"Error scraping data for {domain}: {e}")
            logging.error(f"Error scraping {domain}: {e}")
    return domain_data

def show_domain_data():
    if st.session_state.domain_data:
        cols = st.columns(3)
        for i, data in enumerate(st.session_state.domain_data):
            with cols[i % 3].expander(data["domain"]):
                outreach_subject = st.text_input(f"Subject for {data['domain']}", f"Backlink Opportunity for {data['domain']}", key=f"subject_{data['domain']}")
                outreach_email = st.text_area(f"Outreach Email for {data['domain']}", data["outreach_email"], height=200, key=f"outreach_email_{data['domain']}")
                selected_email = st.text_input(f"Email to send outreach for {data['domain']}", data["suggested_email"], key=f"selected_email_{data['domain']}")
                send_email = st.button(f"Send Email for {data['domain']}", key=f"send_email_{data['domain']}")
                if send_email and not st.session_state.emails_sent.get(data["domain"], False):
                    send_outreach_email(data["domain"], outreach_subject, outreach_email, selected_email)
                    st.session_state.emails_sent[data["domain"]] = True
    else:
        st.warning("No domain data available. Please scrape some domains first.")

def send_outreach_email(domain_name, outreach_subject, outreach_email, selected_email):
    success_count = 0
    for smtp_config in st.session_state.smtp_configs:
        try:
            smtp = smtplib.SMTP_SSL(smtp_config["server"], smtp_config["port"]) if smtp_config["port"] == 465 else smtplib.SMTP(smtp_config["server"], smtp_config["port"])
            smtp.starttls() if smtp_config["port"] != 465 else None
            smtp.login(smtp_config["username"], smtp_config["password"])
            msg = MIMEText(outreach_email)
            msg['Subject'] = outreach_subject
            msg['From'] = smtp_config["sender_email"]
            msg['To'] = selected_email
            smtp.send_message(msg)
            success_count += 1
            smtp.quit()
            st.success(f"Email sent successfully using SMTP configuration: {smtp_config['server']}, {smtp_config['username']}")
            break  # Exit the loop after a successful email send
        except Exception as e:
            st.error(f"Error sending email using SMTP configuration: {smtp_config['server']}, {smtp_config['username']}: {e}")

    if success_count == 0:
        st.warning(f"Email could not be sent for {domain_name} using any of the provided SMTP configurations.")

if st.button("Scrape SERPs"):
    domains = scrape_serps(keywords)
    st.session_state.domain_data = scrape_domains(domains)

show_domain_data()
