from flask import Flask, jsonify, request
import requests
import re
from bs4 import BeautifulSoup, SoupStrainer
from flask_cors import CORS
import urllib.request
from time import time
import cv2
import numpy as np
from collections import defaultdict
# from textblob import TextBlob
from spellchecker import SpellChecker
from urllib.parse import urlparse, urlunparse
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

def get_links_from_website(html_code):
    link_list = []
    for link in BeautifulSoup(html_code, 'html.parser', parse_only=SoupStrainer('a')):
        if link.has_attr('href'):
            link_text = link.text.strip()  # Get the text of the link
            if link_text:
                link_list.append((link['href'], link_text))
    return link_list

def check_url_content(link_list):
    No_Content_Links = []
    Invalid_Links = []
    Valid_Links=[]
    for link in link_list:
        try:
            response = requests.get(link[0])
            link_with_status=(link[0],link[1],response.status_code)
            if response.status_code == 200:  
                if not response.text:
                    No_Content_Links.append(link_with_status)
                else:
                    Valid_Links.append(link_with_status)
            else:
                Invalid_Links.append(link_with_status)  
        except requests.exceptions.RequestException as e:
            link_with_status = (link[0], link[1], str(e))
            Invalid_Links.append(link_with_status)
    return Invalid_Links, No_Content_Links,Valid_Links

def get_misspelled_words(html_code):
    # Parse HTML and extract text
    soup = BeautifulSoup(html_code, 'html.parser')
    text = soup.get_text()
    skip_words = {'idc', 'webinar', 'microsoft', 'whitepaper'}
    # Regex pattern to match URLs
    url_pattern = re.compile(r'https?://\S+')
    # Initialize the spell checker
    spell = SpellChecker()
    
    # Find all words in the text
    words = re.findall(r'\b\w+\b', text)
    all_words_count = len(words)
    correct_words_count = 0
    misspelled_word_with_correct_word = []
    
    for word in words:
        if not word:  # Skip None or empty values
            continue

        lower_word = word.lower()
        # Skip the word if it is in the skip list or if it matches the URL pattern
        if lower_word in skip_words or url_pattern.search(word):
            continue

        # Check if the word is misspelled using SpellChecker
        corrected_word = spell.correction(lower_word)
        if corrected_word == lower_word:
            correct_words_count += 1
        else:
            misspelled_word_with_correct_word.append((lower_word, corrected_word))
    
    
    return all_words_count, correct_words_count, misspelled_word_with_correct_word


def get_image_src_links(html_code):
    src_links = []

    soup = BeautifulSoup(html_code, 'html.parser')
    img_tags = soup.find_all('img')

    for img in img_tags:
        if img.has_attr('src'):
            if(img['src']=='/MS logo.png'):
                src_links.append('https://smt.microsoft.com/MS%20logo.png')
            else:
                src_links.append(img['src'])

    return src_links

def get_image_src_links(html_code):
    src_links = []
    soup = BeautifulSoup(html_code, 'html.parser')
    img_tags = soup.find_all('img')
    
    for img in img_tags:
        if img.has_attr('src'):
            src = img['src']
            if src == '/MS logo.png':
                src_links.append('https://smt.microsoft.com/MS%20logo.png')
            else:
                src_links.append(src)
    
    return src_links

def is_blurry(image_url, threshold=100):
    def calculate_laplacian_variance(image):
        return cv2.Laplacian(image, cv2.CV_64F).var()
    
    def resize_image(image, size=(500, 500)):
        h, w = image.shape[:2]
        if h > w:
            new_h, new_w = size[0], int(size[0] * w / h)
        else:
            new_h, new_w = int(size[1] * h / w), size[1]
        return cv2.resize(image, (new_w, new_h))
    
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            return False
        
        image = resize_image(image)
        laplacian_var = calculate_laplacian_variance(image)
        return laplacian_var < threshold
    except requests.exceptions.RequestException:
        return False

    
def validate_html_w3c(html_code):
    headers = {
        "Content-Type": "text/html; charset=utf-8"
    }
    params = {
        "out": "json"
    }
    response = requests.post("https://validator.w3.org/nu/?out=json", headers=headers, data=html_code, params=params)
    validation_results = response.json()

    messages = validation_results.get('messages', [])
    errors=[]
    warnings=[]
    for message in messages:
        message_type = message.get('type', 'error')  # Default to 'error' if type is not provided
        if message_type == 'error':
            errors.append((message["lastLine"],message['message']))
            
        elif message_type == 'info' and 'subtype' in message and message['subtype'] == 'warning':
            warnings.append((message["lastLine"],message['message']))
    
    return errors,warnings

def get_partial_url(full_url):
    parsed_url = urlparse(full_url)
    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, '', '', '', ''))
    return base_url


@app.route('/check_blurry_images', methods=['POST'])
def check_web_images():
    data = request.get_json()
    html_code = data['code']
    url = data['url']
    blurry_images = []
    
    image_urls = get_image_src_links(html_code)
    
    for image_url in image_urls:
        if image_url.startswith("https://"):
            if is_blurry(image_url):
                blurry_images.append(image_url)
        else:
            partial_url = get_partial_url(url)
            full_image_url = f"{partial_url.rstrip('/')}/{image_url.lstrip('/')}"
            if is_blurry(full_image_url):
                blurry_images.append(full_image_url)
    
    if not blurry_images:
        return jsonify({"Total Images Count":len(image_urls),"Message": "No Blurry Image Found"})
    else:
        return jsonify({"Total Images Count":len(image_urls),"Blurry Images Links": blurry_images})


@app.route('/check_website_links', methods=['POST'])
def check_website_links():
    data = request.get_json()
    html_code = data['code']
    links = get_links_from_website(html_code)
    invalid_links, no_content_links,valid_links= check_url_content(links)
    return jsonify({"Invalid_Links": invalid_links, "No_Content_Links": no_content_links,"Valid Links":valid_links,"Count of Valid Links":len(valid_links),
                    "Count of Invalid Links":len(invalid_links),"Count of Links with no content:":len(no_content_links)})

@app.route('/get_misspelledwords_from_website', methods=['POST'])
def get_misspelledwords_from_website_endpoint():
    data = request.get_json()
    html_code = data['code']
    all_words_count, correct_words_count, misspelled_word_with_correct_word = get_misspelled_words(html_code)
    return jsonify({
        "All Words Count": all_words_count,
        "Correctly Spelled Words Count": correct_words_count,
        "Misspelled Words with Correct Words": misspelled_word_with_correct_word
    })

@app.route('/check_load_time', methods=['POST'])
def check_load_time():
    data = request.get_json()
    url = data['url']
    stream = urllib.request.urlopen(url)
    start_time = time()
    output = stream.read()
    end_time = time()
    stream.close()
    load_time = end_time - start_time
    return jsonify({"Page Load Time is:":load_time})

@app.route('/check_html_errors', methods=['POST'])
def check_htnl_code_errors():
    data = request.get_json()
    html_code = data['code']
    errors,warnings = validate_html_w3c(html_code)
    return jsonify({"Errors": errors, "Warnings": warnings})