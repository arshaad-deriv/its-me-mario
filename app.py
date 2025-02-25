import streamlit as st
import requests
import json
import openai
import time
import tempfile
import os
import zipfile

# Hide the default menu
st.set_page_config(
    page_title="Where's Spidey?", 
    layout="wide"
)

# Initialize session state
if 'site_id' not in st.session_state:
    st.session_state.site_id = ''
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''
if 'openai_key' not in st.session_state:
    st.session_state.openai_key = ''
if 'pages' not in st.session_state:
    st.session_state.pages = []
if 'locales' not in st.session_state:
    st.session_state.locales = []
if 'current_content' not in st.session_state:
    st.session_state.current_content = None
if 'parsed_nodes' not in st.session_state:
    st.session_state.parsed_nodes = None

# Add sidebar configuration
with st.sidebar:
    st.title("Navigation")
    
    # Navigation with radio buttons
    page = st.radio(
        "Select Page",
        ["Page Content", "Static Elements", "CMS Collection Items"],
        index=0,
        key="navigation"
    )
    
    if page == "Static Elements":
        st.switch_page("pages/1_Static_Elements.py")
    elif page == "CMS Collection Items":
        st.switch_page("pages/2_CMS_Collection_Items.py")
    
    st.divider()
    
    # OpenAI Configuration
    st.subheader("OpenAI Configuration")
    openai_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=st.session_state.openai_key,
        help="Your OpenAI API key for translations"
    )
    if openai_key:
        st.session_state.openai_key = openai_key

def get_pages(site_id, api_key):
    """Get list of pages with their IDs"""
    url = f"https://api.webflow.com/v2/sites/{site_id}/pages"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    print(f"\n[DEBUG] Fetching pages from URL: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        pages = response.json()["pages"]
        print(f"[DEBUG] Successfully fetched {len(pages)} pages")
        return pages
    except Exception as e:
        print(f"[DEBUG] Error fetching pages: {str(e)}")
        st.error(f"Error fetching pages: {str(e)}")
        return []

def get_site_locales(site_id, api_key):
    """Get list of locales with their IDs"""
    url = f"https://api.webflow.com/v2/sites/{site_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        locales = []
        # Add primary locale
        primary = data.get('locales', {}).get('primary', {})
        if primary:
            primary['type'] = 'Primary'
            locales.append(primary)
        
        # Add secondary locales
        secondary = data.get('locales', {}).get('secondary', [])
        for locale in secondary:
            locale['type'] = 'Secondary'
            locales.append(locale)
            
        return locales
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        st.error(f"Error fetching site locales: {str(e)}")
        return []

def get_page_content(page_id, api_key):
    """Get page content using DOM endpoint with pagination handling"""
    base_url = f"https://api.webflow.com/v2/pages/{page_id}/dom"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}",
        "accept-version": "1.0.0"
    }
    
    all_nodes = []
    offset = 0
    limit = 100  # Maximum allowed by API
    
    while True:
        # Construct URL with pagination parameters
        url = f"{base_url}?limit={limit}&offset={offset}"
        
        print(f"\nFetching nodes {offset} to {offset + limit}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Add nodes from this batch to our collection
        current_nodes = data.get('nodes', [])
        all_nodes.extend(current_nodes)
        
        # Get pagination info
        pagination = data.get('pagination', {})
        total = pagination.get('total', 0)
        
        print(f"Retrieved {len(current_nodes)} nodes (Total: {len(all_nodes)}/{total})")
        
        # Check if we've got all nodes
        if len(all_nodes) >= total:
            break
            
        # Update offset for next batch
        offset += limit
    
    # Return complete data with all nodes
    return {
        "pageId": data.get("pageId"),
        "nodes": all_nodes,
        "lastUpdated": data.get("lastUpdated")
    }

def validate_api_token(api_key):
    """Validate API token by making a test request"""
    url = "https://api.webflow.com/v2/sites"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Invalid API token. Please check your token and ensure it has the required permissions (pages:read)")
        elif e.response.status_code == 403:
            st.error("API token doesn't have the required permissions. Please ensure it has 'pages:read' scope")
        else:
            st.error(f"API Error: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return False

def parse_page_content(content):
    """Parse page content and extract nodes with property overrides and text nodes"""
    parsed_nodes = []
    
    for node in content.get('nodes', []):
        node_data = {
            "nodeId": node['id'],
            "propertyOverrides": []
        }
        
        # Handle text type nodes
        if node.get('type') == 'text' and 'text' in node:
            node_data["text"] = node['text'].get('html', '')
            parsed_nodes.append(node_data)
            continue
        
        # Handle nodes with property overrides
        if node.get('propertyOverrides'):
            for override in node['propertyOverrides']:
                if 'propertyId' in override and 'text' in override:
                    property_data = {
                        "propertyId": override['propertyId'],
                        "text": override['text'].get('text', '')
                    }
                    node_data["propertyOverrides"].append(property_data)
            
            if node_data["propertyOverrides"]:
                parsed_nodes.append(node_data)
    
    return parsed_nodes

def display_curl_commands(page_id, locale_id, api_key, nodes):
    """Display curl commands for each node"""
    st.subheader("Generated CURL Commands")
    
    for node in nodes:
        for prop in node["propertyOverrides"]:
            curl_command = f"""curl -X POST "https://api.webflow.com/v2/pages/{page_id}/dom?localeId={locale_id}" \\
     -H "Authorization: Bearer {api_key}" \\
     -H "Content-Type: application/json" \\
     -d '{{
  "nodes": [
    {{
      "nodeId": "{node['nodeId']}",
      "propertyOverrides": [
        {{
          "propertyId": "{prop['propertyId']}",
          "text": "{prop['text']}"
        }}
      ]
    }}
  ]
}}'"""
            st.code(curl_command, language="bash")
            st.markdown("---")

def translate_content_with_openai(parsed_nodes, target_language, api_key):
    """Translate content using OpenAI while preserving JSON structure"""
    try:
        # First verify we have valid inputs
        if not parsed_nodes:
            return None, "No content to translate"
        if not target_language:
            return None, "No target language specified"
        if not api_key:
            return None, "OpenAI API key is missing"
            
        client = openai.OpenAI(api_key=api_key)
        
        # Print debug information
        print("\n" + "="*50)
        print("TRANSLATION REQUEST")
        print("="*50)
        print(f"Target Language: {target_language}")
        print("Content to translate:")
        print(json.dumps(parsed_nodes, indent=2))
        
        # Prepare the system message explaining what we want
        system_message = f"""You are a professional translator with 20 years of experience.  
        Translate only the "text" values in the JSON to {target_language}. 
        Follow these rules when translating:

        - When encountering the word "Deriv" and any succeeding word, analyze the context and based on it, keep it in English. For example, "Deriv Blog," "Deriv Life," "Deriv Bot," and "Deriv App" should be kept in English.
        - Keep product names such as P2P, MT5, Deriv X, Deriv cTrader, SmartTrader, Deriv Trader, Deriv GO, Deriv Bot, and Binary Bot in English.
        
        Keep all other JSON structure and values exactly the same.
        Return only the JSON, no explanations."""
        
        # Prepare the JSON for translation
        user_message = f"Translate this JSON content. Original JSON:\n{json.dumps(parsed_nodes, indent=2)}"
        
        # Make the API call with new syntax
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            
            # Print the raw response for debugging
            print("\nOpenAI Response:")
            print(response)
            
            # Extract and validate the response content
            response_content = response.choices[0].message.content
            if not response_content:
                return None, "Empty response from OpenAI"
                
            # Try to parse the JSON response
            try:
                translated_json = json.loads(response_content)
                return translated_json, None
            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {str(e)}")
                print("Raw response content:")
                print(response_content)
                return None, f"Failed to parse OpenAI response as JSON: {str(e)}"
                
        except Exception as e:
            print(f"OpenAI API Error: {str(e)}")
            return None, f"OpenAI API Error: {str(e)}"
            
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return None, f"Translation error: {str(e)}"

def update_page_content(page_id, locale_id, api_key, translated_content):
    """Update page content with translated text"""
    url = f"https://api.webflow.com/v2/pages/{page_id}/dom?localeId={locale_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json"
    }
    
    # Restructure the translated content to match API requirements
    request_body = {
        "nodes": []
    }
    
    # Convert translated content into the correct format
    for node in translated_content:
        node_id = node.get('id') or node.get('nodeId')
        node_data = {
            "nodeId": node_id
        }
        
        # Check if this is a component instance (has propertyOverrides)
        if "propertyOverrides" in node and node["propertyOverrides"]:
            # Only add propertyOverrides if there are actual overrides
            node_data["propertyOverrides"] = [
                {
                    "propertyId": override["propertyId"],
                    "text": override["text"] if isinstance(override["text"], str) 
                           else override["text"].get('text', '')
                }
                for override in node["propertyOverrides"]
            ]
        else:
            # For non-component instances, use text field directly
            node_data["text"] = node.get("text", "")
        
        request_body["nodes"].append(node_data)
    
    print("\n" + "="*50)
    print("UPDATE PAGE CONTENT REQUEST")
    print("="*50)
    print(f"URL: {url}")
    print("\nHeaders:")
    for key, value in headers.items():
        if key.lower() == 'authorization':
            print(f"{key}: Bearer ****{value[-4:]}")
        else:
            print(f"{key}: {value}")
    
    print("\nPayload:")
    print(json.dumps(request_body, indent=2))
    
    try:
        response = requests.post(url, headers=headers, json=request_body)
        
        print("\n" + "="*50)
        print("API RESPONSE")
        print("="*50)
        print(f"Status Code: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
            
        # Check for specific node errors in the response
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("errors"):
                print("\nWarning: Some nodes had errors:")
                for error in response_data["errors"]:
                    print(f"Node {error['nodeId']}: {error['error']}")
        
        response.raise_for_status()
        return True, None
    except Exception as e:
        error_message = str(e)
        print(f"\nERROR: {error_message}")
        return False, error_message

def main():
    st.title("Webflow Page Content Manager")
    
    # Add the image at the top
    st.image("jameson.webp", caption="J. Jonah Jameson")
    
    # Print current session state
    print("\nCurrent Session State:")
    print(f"Has site_id: {bool(st.session_state.site_id)}")
    print(f"Has api_key: {bool(st.session_state.api_key)}")
    print(f"Number of pages: {len(st.session_state.pages)}")
    print(f"Number of locales: {len(st.session_state.locales)}")
    print(f"Has OpenAI key: {bool(st.session_state.openai_key)}")
    print(f"Has current content: {bool(st.session_state.current_content)}")
    
    # Step 1: Get API Token and Site ID
    with st.form("credentials_form"):
        # Add help text for API token
        st.markdown("""
        ### API Token Requirements
        - Must be a valid Webflow API token
        - Requires `pages:read` scope
        - Format: Bearer token
        """)
        
        site_id = st.text_input(
            "Site ID", 
            value=st.session_state.site_id,
            help="The unique identifier for your Webflow site"
        )
        api_key = st.text_input(
            "API Key", 
            type="password", 
            value=st.session_state.api_key,
            help="Your Webflow API token with pages:read scope"
        )
        submit_button = st.form_submit_button("Validate & Fetch Site Data")
    
    if submit_button:
        # First validate the API token
        if validate_api_token(api_key):
            st.success("API token validated successfully!")
            st.session_state.site_id = site_id
            st.session_state.api_key = api_key
            
            # Step 2: Get Pages and Locales
            with st.spinner("Fetching site data..."):
                # Get and display locales
                locales = get_site_locales(site_id, api_key)
                if locales:
                    st.session_state.locales = locales
                    st.subheader("Available Locales")
                    locale_data = {
                        "Type": [locale.get('type', 'Unknown') for locale in locales],
                        "Display Name": [locale.get('displayName', 'Unnamed') for locale in locales],
                        "Locale ID": [locale.get('id', 'No ID') for locale in locales],
                        "Tag": [locale.get('tag', 'No tag') for locale in locales]
                    }
                    st.table(locale_data)
                
                # Uncomment these lines to fetch pages
                pages = get_pages(site_id, api_key)
                if pages:
                    st.session_state.pages = pages
                    st.subheader("Available Pages")
                    page_data = {
                        "Title": [page.get('title', 'Untitled') for page in pages],
                        "Page ID": [page['id'] for page in pages],
                        "Slug": [page.get('slug', 'No slug') for page in pages]
                    }
                    st.table(page_data)
    
    # Page selection and content viewing
    if st.session_state.pages:
        st.subheader("View Page Content")
        selected_page = st.selectbox(
            "Select a page",
            options=[f"{page.get('title', 'Untitled')} ({page['id']})" for page in st.session_state.pages],
            key="page_selector"
        )
        
        if selected_page:
            page_id = selected_page.split('(')[-1].strip(')')
            
            # View content button
            if st.button("View Content", key="view_content_button"):
                with st.spinner("Fetching page content..."):
                    content = get_page_content(page_id, st.session_state.api_key)
                    if content:
                        st.session_state.current_content = content
                        st.session_state.parsed_nodes = parse_page_content(content)
            
            # Display content if available
            if st.session_state.current_content:
                st.subheader("Raw Page Content")
                st.json(st.session_state.current_content)
                
                st.subheader("Parsed Nodes with Property Overrides")
                st.json(st.session_state.parsed_nodes)
                
                # Translation section
                if st.session_state.openai_key and st.session_state.locales:
                    st.subheader("Translate Content")
                    
                    # Add user role selection
                    user_role = st.radio(
                        "Select your role:",
                        ["Designer/Content Writer", "Proofreader"],
                        key="user_role"
                    )

                    # Create language selection with both tag and ID
                    locale_options = {
                        f"{locale.get('displayName', 'Unnamed')} ({locale.get('tag', 'No tag')})": {
                            'tag': locale.get('tag', 'unknown'),
                            'id': locale.get('id')
                        }
                        for locale in st.session_state.locales
                    }
                    
                    # Multi-select for languages
                    target_languages = st.multiselect(
                        "Select target languages",
                        options=list(locale_options.keys()),
                        key="translate_languages_select"
                    )
                    
                    if st.button("Translate to Selected Languages", key="translate_button"):
                        if not target_languages:
                            st.warning("Please select at least one language")
                            return
                            
                        print(f"\nTranslating to {len(target_languages)} languages")
                        
                        # Create a progress bar
                        progress_bar = st.progress(0)
                        translation_status = st.empty()
                        
                        # Process each language
                        for index, target_language in enumerate(target_languages):
                            translation_status.text(f"Processing {target_language} ({index + 1}/{len(target_languages)})")
                            print(f"\nProcessing language: {target_language}")
                            
                            with st.spinner(f"Translating to {target_language}..."):
                                # Use the language tag for translation
                                translated_content, error = translate_content_with_openai(
                                    st.session_state.parsed_nodes,
                                    locale_options[target_language]['tag'],
                                    st.session_state.openai_key
                                )
                                
                                if error:
                                    st.error(f"Error translating to {target_language}: {error}")
                                    continue
                                
                                # Get the locale ID for the API call
                                locale_id = locale_options[target_language]['id']
                                print(f"\nUsing locale ID: {locale_id}")
                                print(f"Language tag: {locale_options[target_language]['tag']}")
                                
                                # Create an expander for each language's details
                                with st.expander(f"Translation Details - {target_language}", expanded=False):
                                    st.subheader("Translated Content")
                                    st.json(translated_content)
                                
                                # Handle content update based on user role
                                if user_role == "Designer/Content Writer":
                                    # Update the page content immediately
                                    success, error = update_page_content(
                                        page_id=page_id,
                                        locale_id=locale_id,
                                        api_key=st.session_state.api_key,
                                        translated_content=translated_content
                                    )
                                    
                                    if success:
                                        st.success(f"Successfully updated content for {target_language}")
                                    else:
                                        st.error(f"Failed to update content for {target_language}: {error}")
                                else:  # Proofreader role
                                    st.write("### Proofreader Review Required")
                                    st.write("Please review and edit the translations below (if required), then click the button to push the update to Webflow.")

                                    # Create two columns for side-by-side view
                                    col1, col2 = st.columns(2)

                                    with col1:
                                        st.subheader("JSON Structure")
                                        # Show the full JSON structure
                                        edited_translation_str = st.text_area(
                                            "Full JSON (for advanced editing)",
                                            value=json.dumps(translated_content, indent=2),
                                            height=300,
                                            key=f"translation_edit_json_{index}"
                                        )

                                    with col2:
                                        st.subheader("Translations Only")
                                        # Extract and display only the text fields for easier editing
                                        translations = []
                                        for node in translated_content:
                                            for override in node.get('propertyOverrides', []):
                                                if 'text' in override:
                                                    translations.append(override['text'])
                                        
                                        # Join translations with newlines for readability
                                        translation_text = '\n'.join(translations)
                                        edited_translations = st.text_area(
                                            "Edit Translations",
                                            value=translation_text,
                                            height=300,
                                            key=f"translation_edit_text_{index}"
                                        )

                                    try:
                                        # Only update if there are actual changes
                                        if edited_translations != translation_text:
                                            print(f"\nUpdating translations. Original:\n{translation_text}\nEdited:\n{edited_translations}")
                                            
                                            edited_translations_list = edited_translations.split('\n')
                                            translation_index = 0
                                            
                                            # Create a deep copy of the original content
                                            updated_content = json.loads(json.dumps(translated_content))
                                            
                                            # Update the translations in the JSON structure
                                            for node in updated_content:
                                                for override in node.get('propertyOverrides', []):
                                                    if 'text' in override and translation_index < len(edited_translations_list):
                                                        override['text'] = edited_translations_list[translation_index].strip()
                                                        translation_index += 1
                                            
                                            # Update the JSON string
                                            edited_translation_str = json.dumps(updated_content, indent=2)
                                            print(f"\nUpdated JSON structure:\n{edited_translation_str}")
                                    except Exception as e:
                                        st.error(f"Error updating translations: {str(e)}")
                                        print(f"\nError while updating translations: {str(e)}")
                                    
                                    if st.button(f"Approve and Push to Webflow - {target_language}", key=f"approve_{index}"):
                                        try:
                                            # Use the appropriate content based on which was last edited
                                            final_content = json.loads(edited_translation_str)
                                            
                                            print("\nSending to Webflow:")
                                            print(json.dumps(final_content, indent=2))
                                            
                                            success, error = update_page_content(
                                                page_id=page_id,
                                                locale_id=locale_id,
                                                api_key=st.session_state.api_key,
                                                translated_content=final_content
                                            )
                                            
                                            if success:
                                                st.success(f"Successfully updated content for {target_language}")
                                            else:
                                                st.error(f"Failed to update content for {target_language}: {error}")
                                        except json.JSONDecodeError as e:
                                            st.error(f"Invalid JSON format: {str(e)}")
                                            print(f"\nJSON Decode Error: {str(e)}")
                                            print(f"Problematic JSON:\n{edited_translation_str}")
                                        except Exception as e:
                                            st.error(f"Error during update: {str(e)}")
                                
                                # Update progress
                                progress = (index + 1) / len(target_languages)
                                progress_bar.progress(progress)
                                
                                # Add a small delay between requests to avoid rate limits
                                time.sleep(1)
                        
                        translation_status.text("All translations completed!")
                        
                else:
                    if not st.session_state.openai_key:
                        st.warning("Please add your OpenAI API key in the sidebar to enable translations")
                    if not st.session_state.locales:
                        st.warning("No locales available for translation")

if __name__ == "__main__":
    main()