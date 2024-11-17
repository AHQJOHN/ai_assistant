import streamlit as st
import re
from datetime import datetime
import sqlite3

# Try importing speech recognition, but provide fallback if not available
SPEECH_RECOGNITION_AVAILABLE = False
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    pass

def init_db():
    conn = sqlite3.connect('expense_requests.db')
    c = conn.cursor()
    c.execute(''' 
        CREATE TABLE IF NOT EXISTS requests 
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         project_name TEXT,
         project_number TEXT,
         amount REAL,
         currency TEXT,
         reason TEXT,
         timestamp DATETIME,
         status TEXT)
    ''')
    conn.commit()
    conn.close()

def extract_project_info(text):
    project_number_match = re.search(r'\b(?:PRJ-|P)?\d{1,}\b', text)
    project_number = project_number_match.group() if project_number_match else None
    project_name_match = re.search(r'(?:project\s+)?([a-zA-Z0-9_\-]+)', text, re.IGNORECASE)
    project_name = project_name_match.group(1) if project_name_match else None
    return project_name, project_number

def extract_amount(text):
    match = re.search(r'\b(\d+(?:\.\d{1,2})?)\s*(USD|EUR|GBP|dollars|euros|pounds)?\b', text, re.IGNORECASE)
    if match:
        amount = float(match.group(1))
        currency = match.group(2) if match.group(2) else 'USD'  # Default to USD if no currency
        return amount, currency
    return None, None

def transcribe_audio_file(audio_file):
    if not SPEECH_RECOGNITION_AVAILABLE:
        return "Speech recognition is not available. Please install the required packages."
    try:
        r = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio = r.record(source)
            text = r.recognize_google(audio)
            return text
    except Exception as e:
        return f"Error processing audio file: {str(e)}"

def transcribe_microphone():
    if not SPEECH_RECOGNITION_AVAILABLE:
        return "Speech recognition is not available. Please install the required packages."
    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=1)
            st.write("🎙️ Listening... Please speak.")
            audio = r.listen(source, timeout=10, phrase_time_limit=15)
            return r.recognize_google(audio)
    except Exception as e:
        return f"Error: {str(e)}"

def process_request(text):
    add_message(text, "user")

    # Initialize session state variables if not already present
    if 'stage' not in st.session_state:
        st.session_state['stage'] = 'project'
    if 'request' not in st.session_state:
        st.session_state['request'] = {}

    # Normalize the input to lowercase for easier comparison
    text = text.lower()

    # Check if 'yes' or other affirmative responses are present
    affirmative_responses = ['yes', 'sure', 'ok', 'affirmative', 'yep', 'yeah', 'proceed']
    if any(response in text for response in affirmative_responses):
        if st.session_state['stage'] == 'confirm':
            save_request()
            # Reset chat after successful request submission
            st.session_state['stage'] = 'project'
            st.session_state['request'] = {}
            add_message("✅ Request submitted successfully!", "assistant")
            add_message("💬 You can start a new request now.", "assistant")
            # Clear previous messages after submission
            st.session_state.messages = []
        return

    if st.session_state['stage'] == 'project':
        project_name, project_number = extract_project_info(text)
        if project_number:
            st.session_state['request']['project_name'] = project_name or "Unnamed Project"
            st.session_state['request']['project_number'] = project_number
            st.session_state['stage'] = 'amount'
            add_message(f"✅ Project info: {project_name or 'Unnamed Project'} ({project_number})", "assistant")
            add_message("💬 Please specify the amount.", "assistant")
        else:
            add_message("💬 I couldn't detect a project number. Please mention it explicitly.", "assistant")
    elif st.session_state['stage'] == 'amount':
        amount, currency = extract_amount(text)
        if amount:
            st.session_state['request']['amount'] = amount
            st.session_state['request']['currency'] = currency
            st.session_state['stage'] = 'reason'
            add_message(f"✅ Amount received: {amount} {currency}", "assistant")
            add_message("💬 What’s the reason for this expense?", "assistant")
        else:
            add_message("💬 Couldn’t detect an amount. Please specify it.", "assistant")
    elif st.session_state['stage'] == 'reason':
        if len(text.split()) >= 3:
            st.session_state['request']['reason'] = text
            st.session_state['stage'] = 'confirm'
            display_summary()
        else:
            add_message("💬 Please provide a more detailed reason for the expense.", "assistant")
    elif st.session_state['stage'] == 'confirm':
        if text.lower() in ['no', 'cancel']:
            st.session_state['stage'] = 'project'
            st.session_state['request'] = {}
            add_message("🔄 Request cancelled. Let’s start over.", "assistant")
        else:
            add_message("💬 Please confirm with 'yes' or 'no'.", "assistant")

def display_summary():
    summary = f"""
    📋 **Summary of your request:**
    - **Project Name**: {st.session_state.request.get('project_name')}
    - **Project Number**: {st.session_state.request.get('project_number')}
    - **Amount**: {st.session_state.request.get('amount')} {st.session_state.request.get('currency')}
    - **Reason**: {st.session_state.request.get('reason')}
    💬 Is this correct? (yes/no)
    """
    add_message(summary, "assistant")

def save_request():
    conn = sqlite3.connect('expense_requests.db')
    c = conn.cursor()
    c.execute(''' 
        INSERT INTO requests 
        (project_name, project_number, amount, currency, reason, timestamp, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        st.session_state.request.get('project_name'),
        st.session_state.request.get('project_number'),
        st.session_state.request.get('amount'),
        st.session_state.request.get('currency'),
        st.session_state.request.get('reason'),
        datetime.now(),
        'Pending'
    ))
    conn.commit()
    conn.close()

def add_message(text, sender):
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    st.session_state.messages.append({"text": text, "sender": sender})

def display_chat_history():
    for message in st.session_state.messages:
        st.write(f'**{"👤 You" if message["sender"] == "user" else "🤖 Assistant"}**: {message["text"]}')

def display_previous_submissions():
    conn = sqlite3.connect('expense_requests.db')
    c = conn.cursor()
    c.execute('SELECT project_name, project_number, amount, currency, reason, timestamp, status FROM requests ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    
    if rows:
        for row in rows:
            st.sidebar.write(f"**Project Name**: {row[0]} | **Project Number**: {row[1]} | **Amount**: {row[2]} {row[3]} | **Reason**: {row[4]} | **Status**: {row[6]} | **Timestamp**: {row[5]}")
    else:
        st.sidebar.write("No previous submissions.")

def main():
    st.title("Expense Request Assistant")
    init_db()
    
    # Display previous submissions in the sidebar
    display_previous_submissions()

    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.stage = 'project'
        add_message("👋 Welcome! Please provide the project information (name or number).", "assistant")
    
    display_chat_history()

    user_input = st.text_input("Type here or upload audio below:")
    if st.button("Submit"):
        process_request(user_input)

    audio_file = st.file_uploader("Upload an audio file", type=["wav", "mp3"])
    if audio_file:
        text = transcribe_audio_file(audio_file)
        process_request(text)

    if SPEECH_RECOGNITION_AVAILABLE and st.button("Record via Microphone"):
        text = transcribe_microphone()
        if text:
            process_request(text)

if __name__ == '__main__':
    main()











# import streamlit as st
# import re
# from datetime import datetime
# import sqlite3

# # Try importing speech recognition, but provide fallback if not available
# SPEECH_RECOGNITION_AVAILABLE = False
# try:
#     import speech_recognition as sr
#     SPEECH_RECOGNITION_AVAILABLE = True
# except ImportError:
#     pass

# def init_db():
#     conn = sqlite3.connect('expense_requests.db')
#     c = conn.cursor()
#     c.execute('''
#         CREATE TABLE IF NOT EXISTS requests
#         (id INTEGER PRIMARY KEY AUTOINCREMENT,
#          project_name TEXT,
#          project_number TEXT,
#          amount REAL,
#          currency TEXT,
#          reason TEXT,
#          timestamp DATETIME,
#          status TEXT)
#     ''')
#     conn.commit()
#     conn.close()

# def extract_project_info(text):
#     project_number_match = re.search(r'\b(?:PRJ-|P)?\d{1,}\b', text)
#     project_number = project_number_match.group() if project_number_match else None
#     project_name_match = re.search(r'(?:project\s+)?([a-zA-Z0-9_\-]+)', text, re.IGNORECASE)
#     project_name = project_name_match.group(1) if project_name_match else None
#     return project_name, project_number

# def extract_amount(text):
#     match = re.search(r'\b(\d+(?:\.\d{1,2})?)\s*(USD|EUR|GBP|dollars|euros|pounds)?\b', text, re.IGNORECASE)
#     if match:
#         amount = float(match.group(1))
#         currency = match.group(2) if match.group(2) else 'USD'  # Default to USD if no currency
#         return amount, currency
#     return None, None

# def transcribe_audio_file(audio_file):
#     if not SPEECH_RECOGNITION_AVAILABLE:
#         return "Speech recognition is not available. Please install the required packages."
#     try:
#         r = sr.Recognizer()
#         with sr.AudioFile(audio_file) as source:
#             audio = r.record(source)
#             text = r.recognize_google(audio)
#             return text
#     except Exception as e:
#         return f"Error processing audio file: {str(e)}"

# def transcribe_microphone():
#     if not SPEECH_RECOGNITION_AVAILABLE:
#         return "Speech recognition is not available. Please install the required packages."
#     try:
#         r = sr.Recognizer()
#         with sr.Microphone() as source:
#             r.adjust_for_ambient_noise(source, duration=1)
#             st.write("🎙️ Listening... Please speak.")
#             audio = r.listen(source, timeout=10, phrase_time_limit=15)
#             return r.recognize_google(audio)
#     except Exception as e:
#         return f"Error: {str(e)}"

# # def process_request(text):
# #     add_message(text, "user")
# #     if 'stage' not in st.session_state:
# #         st.session_state.stage = 'project'
# #         st.session_state.request = {}
    
# #     if st.session_state.stage == 'project':
# #         project_name, project_number = extract_project_info(text)
# #         if project_number:
# #             st.session_state.request['project_name'] = project_name or "Unnamed Project"
# #             st.session_state.request['project_number'] = project_number
# #             st.session_state.stage = 'amount'
# #             add_message(f"✅ Project info: {project_name or 'Unnamed Project'} ({project_number})", "assistant")
# #             add_message("💬 Please specify the amount.", "assistant")
# #         else:
# #             add_message("💬 I couldn't detect a project number. Please mention it explicitly.", "assistant")
# #     elif st.session_state.stage == 'amount':
# #         amount, currency = extract_amount(text)
# #         if amount:
# #             st.session_state.request['amount'] = amount
# #             st.session_state.request['currency'] = currency
# #             st.session_state.stage = 'reason'
# #             add_message(f"✅ Amount received: {amount} {currency}", "assistant")
# #             add_message("💬 What’s the reason for this expense?", "assistant")
# #         else:
# #             add_message("💬 Couldn’t detect an amount. Please specify it.", "assistant")
# #     elif st.session_state.stage == 'reason':
# #         if len(text.split()) >= 3:
# #             st.session_state.request['reason'] = text
# #             st.session_state.stage = 'confirm'
# #             display_summary()
# #         else:
# #             add_message("💬 Please provide a more detailed reason for the expense.", "assistant")
# #     elif st.session_state.stage == 'confirm':
# #         if text.lower() in ['yes', 'confirm', 'proceed']:
# #             save_request()
# #             st.session_state.stage = 'project'
# #             st.session_state.request = {}
# #             add_message("✅ Request submitted successfully!", "assistant")
# #             add_message("💬 You can start a new request now.", "assistant")
# #         elif text.lower() in ['no', 'cancel']:
# #             st.session_state.stage = 'project'
# #             st.session_state.request = {}
# #             add_message("🔄 Request cancelled. Let’s start over.", "assistant")
# #         else:
# #             add_message("💬 Please confirm with 'yes' or 'no'.", "assistant")
# def process_request(text):
#     add_message(text, "user")

#     # Initialize session state variables if not already present
#     if 'stage' not in st.session_state:
#         st.session_state['stage'] = 'project'
#     if 'request' not in st.session_state:
#         st.session_state['request'] = {}

#     # Normalize the input to lowercase for easier comparison
#     text = text.lower()

#     # Check if 'yes' or other affirmative responses are present
#     affirmative_responses = ['yes', 'sure', 'ok', 'affirmative', 'yep', 'yeah', 'proceed']
#     if any(response in text for response in affirmative_responses):
#         if st.session_state['stage'] == 'confirm':
#             save_request()
#             st.session_state['stage'] = 'project'
#             st.session_state['request'] = {}
#             add_message("✅ Request submitted successfully!", "assistant")
#             add_message("💬 You can start a new request now.", "assistant")
#         return

#     if st.session_state['stage'] == 'project':
#         project_name, project_number = extract_project_info(text)
#         if project_number:
#             st.session_state['request']['project_name'] = project_name or "Unnamed Project"
#             st.session_state['request']['project_number'] = project_number
#             st.session_state['stage'] = 'amount'
#             add_message(f"✅ Project info: {project_name or 'Unnamed Project'} ({project_number})", "assistant")
#             add_message("💬 Please specify the amount.", "assistant")
#         else:
#             add_message("💬 I couldn't detect a project number. Please mention it explicitly.", "assistant")
#     elif st.session_state['stage'] == 'amount':
#         amount, currency = extract_amount(text)
#         if amount:
#             st.session_state['request']['amount'] = amount
#             st.session_state['request']['currency'] = currency
#             st.session_state['stage'] = 'reason'
#             add_message(f"✅ Amount received: {amount} {currency}", "assistant")
#             add_message("💬 What’s the reason for this expense?", "assistant")
#         else:
#             add_message("💬 Couldn’t detect an amount. Please specify it.", "assistant")
#     elif st.session_state['stage'] == 'reason':
#         if len(text.split()) >= 3:
#             st.session_state['request']['reason'] = text
#             st.session_state['stage'] = 'confirm'
#             display_summary()
#         else:
#             add_message("💬 Please provide a more detailed reason for the expense.", "assistant")
#     elif st.session_state['stage'] == 'confirm':
#         if text.lower() in ['no', 'cancel']:
#             st.session_state['stage'] = 'project'
#             st.session_state['request'] = {}
#             add_message("🔄 Request cancelled. Let’s start over.", "assistant")
#         else:
#             add_message("💬 Please confirm with 'yes' or 'no'.", "assistant")



# def display_summary():
#     summary = f"""
#     📋 **Summary of your request:**
#     - **Project Name**: {st.session_state.request.get('project_name')}
#     - **Project Number**: {st.session_state.request.get('project_number')}
#     - **Amount**: {st.session_state.request.get('amount')} {st.session_state.request.get('currency')}
#     - **Reason**: {st.session_state.request.get('reason')}
#     💬 Is this correct? (yes/no)
#     """
#     add_message(summary, "assistant")

# def save_request():
#     conn = sqlite3.connect('expense_requests.db')
#     c = conn.cursor()
#     c.execute('''
#         INSERT INTO requests 
#         (project_name, project_number, amount, currency, reason, timestamp, status)
#         VALUES (?, ?, ?, ?, ?, ?, ?)
#     ''', (
#         st.session_state.request.get('project_name'),
#         st.session_state.request.get('project_number'),
#         st.session_state.request.get('amount'),
#         st.session_state.request.get('currency'),
#         st.session_state.request.get('reason'),
#         datetime.now(),
#         'Pending'
#     ))
#     conn.commit()
#     conn.close()

# def add_message(text, sender):
#     if 'messages' not in st.session_state:
#         st.session_state.messages = []
#     st.session_state.messages.append({"text": text, "sender": sender})

# def display_chat_history():
#     for message in st.session_state.messages:
#         st.write(f'**{"👤 You" if message["sender"] == "user" else "🤖 Assistant"}**: {message["text"]}')

# def main():
#     st.title("Expense Request Assistant")
#     init_db()
    
#     if 'messages' not in st.session_state:
#         st.session_state.messages = []
#         st.session_state.stage = 'project'
#         add_message("👋 Welcome! Please provide the project information (name or number).", "assistant")
    
#     display_chat_history()

#     user_input = st.text_input("Type here or upload audio below:")
#     if st.button("Submit"):
#         process_request(user_input)

#     audio_file = st.file_uploader("Upload an audio file", type=["wav", "mp3"])
#     if audio_file:
#         text = transcribe_audio_file(audio_file)
#         process_request(text)

#     if SPEECH_RECOGNITION_AVAILABLE and st.button("Record via Microphone"):
#         text = transcribe_microphone()
#         if text:
#             process_request(text)

# if __name__ == '__main__':
#     main()
