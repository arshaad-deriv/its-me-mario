import streamlit as st
import requests
import json
import openai
import logging

# Set up logging configuration at the top of the file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Hide the default menu
st.set_page_config(
    page_title="J.Jonah Jameson - Get it to the front page",
    layout="wide"
)

def get_cms_locales(site_id, api_key):
    """Get list of CMS locales from site data"""
    url = f"https://api.webflow.com/v2/sites/{site_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        cms_locales = []
        
        # Add primary locale
        primary = data.get('locales', {}).get('primary', {})
        if primary:
            cms_locales.append({
                'name': primary.get('displayName', 'Unnamed'),
                'id': primary.get('cmsLocaleId'),
                'code': primary.get('tag'),
                'default': True
            })
        
        # Add secondary locales
        secondary = data.get('locales', {}).get('secondary', [])
        for locale in secondary:
            if locale.get('enabled', False):  # Only include enabled locales
                cms_locales.append({
                    'name': locale.get('displayName', 'Unnamed'),
                    'id': locale.get('cmsLocaleId'),
                    'code': locale.get('tag'),
                    'default': False
                })
        
        return cms_locales
    except Exception as e:
        st.error(f"Error fetching CMS locales: {str(e)}")
        return []

def get_collection_items(site_id, collection_id, api_key, offset=0, limit=100):
    """Get collection items with optional filtering"""
    url = f"https://api.webflow.com/v2/collections/{collection_id}/items"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    params = {
        "offset": offset,
        "limit": limit
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching collection items: {str(e)}")
        return None

def translate_collection_item(collection_id, item_id, api_key, cms_locale_id):
    """Get translated version of a collection item"""
    url = f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    # Add the CMS Locale ID as a query parameter
    params = {
        "cmsLocaleId": cms_locale_id
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json(), None
    except Exception as e:
        return None, f"Error fetching translation: {str(e)}"

def update_collection_item(collection_id, item_id, api_key, cms_locale_id, field_data):
    """Update a collection item with translated content"""
    url = f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json"
    }
    
    # Prepare the payload
    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": field_data,
        "cmsLocaleId": cms_locale_id
    }
    
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json(), None
    except Exception as e:
        return None, f"Error updating translation: {str(e)}"

def generate_curl_command(collection_id, item_id, api_key, cms_locale_id, field_data):
    """Generate curl command for updating translation"""
    # Prepare the payload with proper escaping for curl
    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": field_data,
        "cmsLocaleId": cms_locale_id
    }
    
    # Create the curl command
    curl_command = f"""curl -X PATCH "https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}" \\
     -H "Authorization: Bearer {api_key}" \\
     -H "Content-Type: application/json" \\
     -d '{json.dumps(payload, ensure_ascii=False)}'"""
    
    return curl_command

def translate_with_openai(text, target_language, api_key):
    """Translate text using OpenAI"""
    try:
        logger.info(f"\n{'='*50}\nTRANSLATING TO {target_language}\n{'='*50}")
        logger.info(f"Original text:\n{text[:200]}..." if len(text) > 200 else text)
        
        client = openai.OpenAI(api_key=api_key)
        
        system_message = f"""You are a professional translator with 20 years of experience.
        Translate the text to {target_language}.
        Follow these rules when translating:
        - When encountering the word "Deriv" and any succeeding word, keep it in English. For example, "Deriv Blog," "Deriv Life," "Deriv Bot," and "Deriv App" should be kept in English.
        - Keep product names such as P2P, MT5, Deriv X, Deriv cTrader, SmartTrader, Deriv Trader, Deriv GO, Deriv Bot, and Binary Bot in English.
        Return only the translation, no explanations."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        
        translated_text = response.choices[0].message.content.strip()
        logger.info(f"Translated text:\n{translated_text[:200]}..." if len(translated_text) > 200 else translated_text)
        logger.info(f"{'='*50}\n")
        
        return translated_text, None
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return None, f"Translation error: {str(e)}"

def execute_curl_command(collection_id, item_id, api_key, cms_locale_id, field_data):
    """Execute the PATCH request and return response"""
    url = f"https://api.webflow.com/v2/collections/{collection_id}/items/{item_id}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json"
    }
    
    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": field_data,
        "cmsLocaleId": cms_locale_id
    }
    
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        return {
            'status_code': response.status_code,
            'response': response.json(),
            'error': None
        }
    except Exception as e:
        return {
            'status_code': None,
            'response': None,
            'error': str(e)
        }

def get_collections(site_id, api_key):
    """Get list of collections from the site"""
    url = f"https://api.webflow.com/v2/sites/{site_id}/collections"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('collections', [])
    except Exception as e:
        st.error(f"Error fetching collections: {str(e)}")
        return []

def main():
    st.title("J.Jonah Jameson - Get it to the front page")
    
    # Check if we have the required credentials
    if not st.session_state.get('site_id') or not st.session_state.get('api_key'):
        st.error("Please enter your Site ID and API Key in the main page first")
        return
    
    if not st.session_state.get('openai_key'):
        st.warning("Please add your OpenAI API key in the sidebar to enable translations")
        return
    
    # Display CMS locales table
    st.subheader("CMS Locales")
    with st.spinner("Fetching CMS locales..."):
        cms_locales = get_cms_locales(st.session_state.site_id, st.session_state.api_key)
        if cms_locales:
            locale_data = {
                "Language": [locale.get('name', 'Unnamed') for locale in cms_locales],
                "CMS Locale ID": [locale.get('id', 'No ID') for locale in cms_locales],
                "Language Code": [locale.get('code', 'No code') for locale in cms_locales],
                "Default": [str(locale.get('default', False)) for locale in cms_locales]
            }
            st.table(locale_data)
    
    # Replace Collection ID input with dropdown
    st.subheader("Collection Details")
    with st.spinner("Fetching collections..."):
        collections = get_collections(st.session_state.site_id, st.session_state.api_key)
        if collections:
            collection_options = [f"{col['displayName']} ({col['id']})" for col in collections]
            selected_collection = st.selectbox(
                "Select Collection",
                options=collection_options,
                help="Choose the collection you want to manage"
            )
            
            if selected_collection:
                # Extract collection ID from the selection
                collection_id = selected_collection.split('(')[-1].strip(')')
                
                # Get collection items
                with st.spinner("Fetching collection items..."):
                    items = get_collection_items(
                        st.session_state.site_id,
                        collection_id,
                        st.session_state.api_key
                    )
                    
                    if items and 'items' in items:
                        # Create a filter for slugs with more meaningful names
                        all_items = [(
                            item.get('fieldData', {}).get('name', 'Unnamed'),
                            item.get('fieldData', {}).get('slug', 'no-slug'),
                            item.get('id')
                        ) for item in items['items']]
                        
                        selected_item_name = st.selectbox(
                            "Filter by Content",
                            options=['All'] + [f"{name} ({slug})" for name, slug, _ in all_items]
                        )
                        
                        # Initialize selected_data
                        selected_data = None
                        
                        # Filter items based on selection
                        if selected_item_name != 'All':
                            selected_slug = selected_item_name.split('(')[-1].strip(')')
                            selected_data = next(
                                (item for item in items['items'] 
                                if item.get('fieldData', {}).get('slug') == selected_slug),
                                None
                            )
                        
                            if selected_data:
                                # Extract relevant fields from the original item
                                original_field_data = selected_data.get('fieldData', {})
                                relevant_keys = [
                                    'disclaimer-2',
                                    'post',
                                    'summary',
                                    'name',
                                    'meta-description-2',
                                    'page-title',
                                    'accumulators-option',
                                    'slug'
                                ]
                                
                                # Create a filtered dictionary with only relevant keys
                                filtered_data = {
                                    key: original_field_data.get(key, '')
                                    for key in relevant_keys
                                    if key in original_field_data
                                }
                                
                                st.subheader("Original Content")
                                st.json(filtered_data)
                                
                                # Translation section
                                st.subheader("Translation Management")
                                
                                # Add translation mode selection
                                translation_mode = st.radio(
                                    "Translation Mode",
                                    ["Single Language", "All Languages"],
                                    help="Choose to translate to one language or all available languages"
                                )
                                
                                if translation_mode == "Single Language":
                                    # Existing single language translation logic
                                    target_language = st.selectbox(
                                        "Select target language",
                                        options=[f"{locale['name']} ({locale['code']}) - {locale['id']}" 
                                                for locale in cms_locales]
                                    )
                                    
                                    if target_language:
                                        # Extract CMS Locale ID and language code
                                        cms_locale_id = target_language.split(' - ')[-1]
                                        language_code = target_language.split('(')[1].split(')')[0]
                                        
                                        # Display form with translations
                                        with st.form("translation_form"):
                                            edited_fields = {}
                                            
                                            for key, value in filtered_data.items():
                                                if key in ['slug', 'accumulators-option']:
                                                    edited_fields[key] = value
                                                    continue
                                                
                                                if isinstance(value, str):
                                                    # Use translated text if available, otherwise use original
                                                    display_text = st.session_state.get('translations', {}).get(key, value)
                                                    
                                                    if len(value) > 200:
                                                        edited_fields[key] = st.text_area(
                                                            key,
                                                            value=display_text,
                                                            height=300
                                                        )
                                                    else:
                                                        edited_fields[key] = st.text_input(
                                                            key,
                                                            value=display_text
                                                        )
                                            
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                translate_button = st.form_submit_button("Translate")
                                            with col2:
                                                update_button = st.form_submit_button("Update Content")
                                            
                                            if translate_button:
                                                with st.spinner("Translating content..."):
                                                    for key, value in filtered_data.items():
                                                        if isinstance(value, str) and key not in ['slug', 'accumulators-option']:
                                                            translated_text, error = translate_with_openai(
                                                                value,
                                                                language_code,
                                                                st.session_state.openai_key
                                                            )
                                                            if error:
                                                                st.error(f"Error translating {key}: {error}")
                                                            else:
                                                                edited_fields[key] = translated_text
                                            
                                            if update_button:
                                                with st.spinner("Updating content..."):
                                                    result = execute_curl_command(
                                                        collection_id=collection_id,
                                                        item_id=selected_data['id'],
                                                        api_key=st.session_state.api_key,
                                                        cms_locale_id=cms_locale_id,
                                                        field_data=edited_fields
                                                    )
                                                    
                                                    if result['error']:
                                                        st.error(f"Error updating content: {result['error']}")
                                                    else:
                                                        st.success("✅ Content updated successfully!")
                                
                                else:  # All Languages mode
                                    if st.button("Translate and Update All Languages"):
                                        # Create a progress container
                                        progress_container = st.empty()
                                        status_container = st.empty()
                                        results_container = st.container()
                                        
                                        # Initialize translation results
                                        translation_results = []
                                        
                                        # Get non-default languages
                                        languages_to_translate = [l for l in cms_locales if not l.get('default', False)]
                                        total_languages = len(languages_to_translate)
                                        
                                        for idx, locale in enumerate(languages_to_translate):
                                            # Update progress (ensure it's between 0 and 1)
                                            progress = min(idx / total_languages, 1.0)
                                            progress_container.progress(progress)
                                            
                                            # Update status message
                                            status_container.info(f"Translating to {locale['name']} ({locale['code']})...")
                                            
                                            # Store translations for this language
                                            current_translations = {}
                                            
                                            # Translate each field
                                            for key, value in filtered_data.items():
                                                if isinstance(value, str) and key not in ['slug', 'accumulators-option']:
                                                    translated_text, error = translate_with_openai(
                                                        value,
                                                        locale['code'],
                                                        st.session_state.openai_key
                                                    )
                                                    if error:
                                                        translation_results.append({
                                                            'language': locale['name'],
                                                            'status': 'error',
                                                            'message': f"Error translating {key}: {error}"
                                                        })
                                                        translated_text = value
                                                    current_translations[key] = translated_text
                                                else:
                                                    current_translations[key] = value
                                            
                                            # Execute update for this language
                                            result = execute_curl_command(
                                                collection_id=collection_id,
                                                item_id=selected_data['id'],
                                                api_key=st.session_state.api_key,
                                                cms_locale_id=locale['id'],
                                                field_data=current_translations
                                            )
                                            
                                            # Store result
                                            translation_results.append({
                                                'language': locale['name'],
                                                'status': 'success' if not result['error'] else 'error',
                                                'message': result['error'] if result['error'] else 'Translation completed successfully'
                                            })
                                            
                                            # Update results in real-time
                                            with results_container:
                                                st.write("Translation Results:")
                                                for result in translation_results:
                                                    if result['status'] == 'success':
                                                        st.success(f"✅ {result['language']}: {result['message']}")
                                                    else:
                                                        st.error(f"❌ {result['language']}: {result['message']}")
                                        
                                        # Clear progress and status when complete
                                        progress_container.empty()
                                        status_container.success("All translations completed!")

if __name__ == "__main__":
    main() 