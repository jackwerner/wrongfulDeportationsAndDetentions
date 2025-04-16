import os
import requests
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import instructor
from anthropic import Anthropic
from pydantic import BaseModel, Field
from typing import Literal
import pandas as pd
import time
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

courtlistener_api_key = os.getenv("COURTLISTENER_API_KEY")
claude_api_key = os.getenv("CLAUDE_API_KEY")  

class CaseAnalysis(BaseModel):
    """Structured output for case analysis"""
    case_title: str = Field(description="The title of the court case")
    person_name: str = Field(description="Name of the person who was deported or detained")
    wrongful_deportation: Literal["yes", "no", "unknown"] = Field(
        description="Whether the case involves a wrongful deportation claim")
    wrongful_detention: Literal["yes", "no", "unknown"] = Field(
        description="Whether the case involves a wrongful detention claim")
    is_us_citizen: Literal["yes", "no", "unknown"] = Field(
        description="Whether the person is a US citizen")
    case_summary: str = Field(description="A summary of the case and its key findings")

def search_courtlistener(fetch_full_text=False, max_pages=None):
    """
    Search CourtListener API for recent immigration-related cases
    
    Args:
        days_back (int): Number of days to look back for cases
        fetch_full_text (bool): Whether to fetch full text for each case
        max_pages (int, optional): Maximum number of pages to fetch. If None, fetch all available pages.
    """
    cases = []
    
    try:
        # CourtListener search
       
        headers = {
            "Authorization": f"Token {courtlistener_api_key}"
        }
        
        # Verify we have the API key
        if not courtlistener_api_key:
            logger.error("CourtListener API key is missing. Set the COURTLISTENER_API_KEY environment variable.")
            return []
            
        # Use March 15th instead of calculating days back
        date_filed_after = "03/15/2024"
        
        # Use direct URL approach with all parameters encoded
        base_url = f"https://www.courtlistener.com/api/rest/v4/search/?q=(%22alien%20enemy%20act%22%20OR%20%22el%20salvador%22%20OR%20%22cecot%22%20OR%20%22terrorism%20confinement%20center%22)%20AND%20(wrongful%20OR%20wrongfully%20OR%20unlawful%20OR%20unlawfully)%20AND%20(deportation%20OR%20deported%20OR%20detention%20OR%20detained%20OR%20removal%20OR%20removed%20OR%20%22habeas%20corpus%22%20OR%20%22due%20process%22%20OR%20%22ICE%22%20OR%20%22Immigration%20and%20Customs%20Enforcement%22%20OR%20%22Department%20of%20Homeland%20Security%22%20OR%20%22DHS%22%20OR%20%22Trump%22%20OR%20%22Noem%22%20OR%20%22DOJ%22%20OR%20%22Trump%20Administration%22)&type=o&order_by=score%20desc&stat_Published=on&stat_Unpublished=on&stat_Errata=on&stat_Separate=on&stat_In-chambers=on&stat_Relating-to=on&stat_Unknown=on&filed_after={date_filed_after}"
        
        # ("alien enemy act" OR "el salvador" OR "cecot" OR "terrorism confinement center") AND (wrongful OR wrongfully OR unlawful OR unlawfully) AND (deportation OR deported OR detention OR detained OR removal OR removed OR "habeas corpus" OR "due process" OR "ICE" OR "Immigration and Customs Enforcement" OR "Department of Homeland Security" OR "DHS" OR "Trump" OR "Noem" OR "DOJ" OR "Trump Administration")

        # Add pagination parameters
        logger.info(f"Making initial request to: {base_url}")
        logger.info(f"Using authorization header: Token {courtlistener_api_key[:4]}...")
        
        next_url = base_url
        page_num = 1
        
        # Continue fetching while there are more pages
        while next_url:
            logger.info(f"Fetching page {page_num} from: {next_url}")
            response = requests.get(next_url, headers=headers)
            
            if response.status_code == 200:
                results = response.json()
                # Log the page results
                logger.info(f"Page {page_num} returned {len(results.get('results', []))} results")
                
                # Process cases from this page
                for i, case in enumerate(results.get('results', [])):
                    # Log the complete case entry
                    logger.info(f"Case {i+1} on page {page_num} details:")
                    logger.info(f"  Case Name: {case.get('caseName')}")
                    
                    # Get the correct opinion ID from the opinions array
                    opinion_id = None
                    if case.get('opinions') and len(case.get('opinions')) > 0:
                        opinion_id = case['opinions'][0].get('id')
                        logger.info(f"  Opinion ID from opinions array: {opinion_id}")
                    
                    # Fallback to cluster_id if no opinion ID is found
                    cluster_id = case.get('cluster_id')
                    # logger.info(f"  Cluster ID: {cluster_id}")
                    
                    # Choose the most reliable ID
                    case_id = opinion_id or cluster_id
                    logger.info(f"  Using ID: {case_id}")
                    
                    case_data = {
                        'case_name': case.get('caseName'),
                        'docket_number': case.get('docketNumber'),
                        'court': case.get('court'),
                        'date_filed': case.get('dateFiled'),
                        'url': case.get('absolute_url'),
                        'case_id': case_id,  # Store the correct opinion ID
                        'text': ''
                    }
                    
                    # Fetch full text if requested
                    if fetch_full_text and case_id:
                        case_data['text'] = get_case_text(case_id, headers, case.get('caseName', ''))
                        
                    cases.append(case_data)
                
                # Check if there are more pages
                next_url = results.get('next')
                if next_url:
                    page_num += 1
                    # Check if we've reached the maximum number of pages
                    if max_pages and page_num > max_pages:
                        logger.info(f"Reached maximum number of pages ({max_pages})")
                        break
                    # Add a small delay to avoid rate limiting
                    time.sleep(1)
                else:
                    logger.info(f"No more pages to fetch")
                    break
            else:
                logger.error(f"Request failed with status: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")  # First 500 chars
                break
        
        logger.info(f"Found a total of {len(cases)} court cases across {page_num} pages")
        return cases
    except Exception as e:
        logger.error(f"Error searching court cases: {str(e)}")
        return []

def get_case_text(case_id, headers, case_name):
    """
    Fetch the full text of a case from CourtListener API
    
    Args:
        case_id (str): ID of the case in CourtListener
        headers (dict): Headers for API request
        case_name (str): Name of the case for verification
    
    Returns:
        str: Full text of the case or empty string if error
    """
    try:
        # Use the case ID directly to fetch the opinion
        api_url = f"https://www.courtlistener.com/api/rest/v4/opinions/{case_id}/"
        
        logger.info(f"Fetching case text for '{case_name}' from: {api_url}")
        
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            case_data = response.json()
            
            # Verify case identity to ensure we have the right text
            api_case_name = case_data.get('case_name', '')
            if api_case_name and not api_case_name.lower() in case_name.lower() and not case_name.lower() in api_case_name.lower():
                logger.warning(f"Case name mismatch! Expected: '{case_name}' but API returned: '{api_case_name}'")
                logger.warning(f"Continuing anyway as ID-based retrieval should be reliable")
            
            # Log the available keys to help debug
            # logger.info(f"Available fields in response: {list(case_data.keys())}")
            
            # Try different possible fields for the text content
            if 'html' in case_data and case_data['html']:
                logger.info(f"Using 'html' field for case text of {case_name}")
                return case_data['html']
            elif 'plain_text' in case_data and case_data['plain_text']:
                # logger.info(f"Using 'plain_text' field for case text of {case_name}")
                return case_data['plain_text']
            elif 'text' in case_data and case_data['text']:
                logger.info(f"Using 'text' field for case text of {case_name}")
                return case_data['text']
            elif 'opinion_text' in case_data and case_data['opinion_text']:
                logger.info(f"Using 'opinion_text' field for case text of {case_name}")
                return case_data['opinion_text']
            else:
                # If no text field is found, log a sample of the response
                logger.warning(f"No text field found for '{case_name}'. Sample data: {str(case_data)[:500]}")
                return ''
        else:
            logger.warning(f"Failed to fetch case text for '{case_name}': Status {response.status_code}")
            logger.warning(f"Response content: {response.text[:500]}")
            return ''
    except Exception as e:
        logger.error(f"Error fetching case text for '{case_name}': {str(e)}")
        return ''

def analyze_case_with_claude(case_text, case_name):
    """
    Analyze a case text using Claude 3.5 Sonnet with structured output
    
    Args:
        case_text (str): The full text of the case
        case_name (str): The name of the case for reference
        
    Returns:
        CaseAnalysis: Structured analysis of the case
    """
    try:
        if not claude_api_key:
            logger.error("Claude API key is missing. Set the CLAUDE_API_KEY environment variable.")
            return None
            
        logger.info(f"Analyzing case: {case_name}")
        
        # Set up Claude client with instructor
        client = Anthropic(api_key=claude_api_key)
        instructor_client = instructor.from_anthropic(client)
        
        # Create prompt for Claude
        prompt = f"""
        You are a legal analyst specializing in immigration law. Please analyze the following court case 
        and extract key information about deportation or detention claims.
        
        Court Case: {case_name}
        
        Case Text:
        {case_text[:100000]}  # Limiting to 100k tokens for Claude context window
        
        Based on this case, please identify whether this involves wrongful deportation or detention,
        the name of the affected person, whether they are a US citizen, and provide a summary of the case.
        If any information is not explicitly stated or unclear, respond with "unknown".
        """
        
        # Get structured response
        response = instructor_client.chat.completions.create(
            model="claude-3-5-sonnet-20240620",
            response_model=CaseAnalysis,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        logger.info(f"Successfully analyzed case: {case_name}")
        return response
    
    except Exception as e:
        logger.error(f"Error analyzing case with Claude: {str(e)}")
        return None

def load_existing_cases(csv_path='courtlistener_cases.csv'):
    """
    Load existing analyzed cases from CSV file
    
    Args:
        csv_path (str): Path to the CSV file
        
    Returns:
        set: Set of docket numbers that have already been processed
        dict: Dictionary mapping docket numbers to their full data
    """
    existing_docket_numbers = set()
    existing_cases_data = {}
    
    try:
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            # Check if docket_number column exists
            if 'docket_number' not in df.columns:
                logger.warning("No 'docket_number' column found in existing CSV. Cannot check for duplicates.")
                return existing_docket_numbers, existing_cases_data
                
            # Create a set of existing docket numbers for quick lookup
            existing_docket_numbers = set(df['docket_number'].dropna().astype(str))
            
            # Create a dictionary for full case data lookup
            for _, row in df.iterrows():
                docket_number = str(row.get('docket_number', ''))
                if docket_number:
                    existing_cases_data[docket_number] = row.to_dict()
            
            logger.info(f"Loaded {len(existing_docket_numbers)} existing cases from {csv_path}")
        else:
            logger.info(f"No existing CSV file found at {csv_path}")
    except Exception as e:
        logger.error(f"Error loading existing cases: {str(e)}")
    
    return existing_docket_numbers, existing_cases_data

if __name__ == "__main__":
    # Load existing cases to avoid duplicates
    csv_path = 'courtlistener_cases.csv'
    existing_docket_numbers, existing_cases_data = load_existing_cases(csv_path)
    
    # Set fetch_full_text=True to get the full text of each case
    cases = search_courtlistener(fetch_full_text=False, max_pages=2)
    
    # Create a list to store analyzed cases
    analyzed_cases = []
    
    # Add existing cases to ensure we don't lose previous data
    for docket_number, case_data in existing_cases_data.items():
        analyzed_cases.append(case_data)
    
    # Process new cases
    for case in cases:
        docket_number = str(case.get('docket_number', ''))
        
        # Skip if case already exists in our dataset
        if docket_number and docket_number in existing_docket_numbers:
            logger.info(f"Skipping already processed case: {case['case_name']} (Docket: {docket_number})")
            continue
        
        case_data = {
            'case_name': case['case_name'],
            'docket_number': docket_number,
            'court': case.get('court', ''),
            'date_filed': case.get('date_filed', ''),
            'url': case['url']
        }
        
        # Only fetch full text for cases we haven't processed before
        if docket_number:
            logger.info(f"Processing new case: {case['case_name']} (Docket: {docket_number})")
            
            # Fetch the full text only if needed
            headers = {
                "Authorization": f"Token {courtlistener_api_key}"
            }
            case_id = case.get('id', '')  # Get the API's case ID for fetching text
            case_text = get_case_text(case_id, headers, case['case_name'])
            
            if case_text:
                logger.info(f"Analyzing case: {case['case_name']}")
                analysis = analyze_case_with_claude(case_text, case['case_name'])
                if analysis:
                    # Add analysis results to case data
                    case_data['case_title'] = analysis.case_title
                    case_data['person_name'] = analysis.person_name
                    case_data['wrongful_deportation'] = analysis.wrongful_deportation
                    case_data['wrongful_detention'] = analysis.wrongful_detention
                    case_data['is_us_citizen'] = analysis.is_us_citizen
                    case_data['case_summary'] = analysis.case_summary
                    logger.info(f"Successfully added analysis for: {case['case_name']}")
                else:
                    # Add empty values for analysis fields
                    case_data['case_title'] = ''
                    case_data['person_name'] = ''
                    case_data['wrongful_deportation'] = ''
                    case_data['wrongful_detention'] = ''
                    case_data['is_us_citizen'] = ''
                    case_data['case_summary'] = ''
                    logger.warning(f"Analysis failed for case: {case['case_name']}")
            else:
                # Add empty values for analysis fields
                case_data['case_title'] = ''
                case_data['person_name'] = ''
                case_data['wrongful_deportation'] = ''
                case_data['wrongful_detention'] = ''
                case_data['is_us_citizen'] = ''
                case_data['case_summary'] = ''
                logger.warning(f"No text available for case: {case['case_name']}")
            
            analyzed_cases.append(case_data)
            # wait 5 seconds
            time.sleep(5)
    
    # Print the analyzed cases for debugging
    new_cases_count = len(analyzed_cases) - len(existing_cases_data)
    logger.info(f"Found {new_cases_count} new cases")
    
    # Save to CSV (all cases - both existing and new)
    df = pd.DataFrame(analyzed_cases)
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved {len(analyzed_cases)} cases to {csv_path}")