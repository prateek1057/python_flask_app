from flask import Flask, jsonify, request
import requests
import re
from bs4 import BeautifulSoup, SoupStrainer
from flask_cors import CORS
import urllib.request
from time import time
import cv2
import numpy as np
import html5lib
from html5lib.html5parser import HTMLParser, ParseError
from io import StringIO
from spellchecker import SpellChecker
from urllib.parse import urlparse, urlunparse
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
 
# Pre-compile the regex pattern
url_pattern = re.compile(r'https?://\S+')
 
# Define skip words set outside the function to avoid re-initializing
skip_words = {'idc', 'webinar', 'microsoft', 'whitepaper'}
 
def get_partial_url(full_url):
    parsed_url = urlparse(full_url)
    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, '', '', '', ''))
    return base_url
 
def get_links_from_website(html_code):
    link_list = []
    for link in BeautifulSoup(html_code, 'html.parser', parse_only=SoupStrainer('a')):
        if link.has_attr('href'):
            link_text = link.text.strip()  # Get the text of the link
            if link_text:
                link_list.append((link['href'], link_text))
    return link_list
 
def check_url_content(link_list, url):
    No_Content_Links = []
    Invalid_Links = []
    Valid_Links=[]
    response = {}
    link_with_status={}
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
    }
    for link in link_list:
        try:
            if link[0].startswith("https://"):
                response = requests.get(link[0],headers=headers)
                response.raise_for_status()
                link_with_status=(link[0],link[1],response.status_code)
            else:
                partial_url = get_partial_url(url)
                full_link_url = f"{partial_url.rstrip('/')}/{link[0].lstrip('/')}"
                response = requests.get(full_link_url,headers=headers)
                response.raise_for_status()
                link_with_status=(full_link_url,link[1],response.status_code)
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
 
def validate_html_w3c(html):
    '''Parse HTML with html5lib and log all errors and warnings.'''
    errors = []
    warnings = []
   
    parser = HTMLParser(strict=True, tree=html5lib.treebuilders.getTreeBuilder("etree"))
    try:
        parsed_tree = parser.parse(StringIO(html))
    except ParseError as e:
        if "Specific Error Message" not in str(e):  # Skip specific error
            errors.append(str(e))
 
    return errors, warnings
 
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
 
   
def validate_html(html):
    soup = BeautifulSoup(html, 'html5lib')
    errors = []
 
    # Check for missing alt attributes in img tags
    for img in soup.find_all('img'):
        if not img.get('alt'):
            errors.append({
                'error': 'Missing alt attribute',
                'element': str(img),
                'message': 'All img tags must have an alt attribute for accessibility.'
            })
 
    # Add more validation checks as needed
    # For example, check for missing title in head, etc.
 
    return errors
 
 
 
 
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
    url = data['url']
    links = get_links_from_website(html_code)
    invalid_links, no_content_links,valid_links= check_url_content(links,url)
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
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as stream:
        start_time = time()
        output = stream.read()
        end_time = time()
    load_time = (end_time - start_time)
    return jsonify({"Page Load Time is:":load_time})
 
 
@app.route('/check_html_errors', methods=['POST'])
def check_htnl_code_errors():
    data = request.get_json()
    html_code = data['code']
    errors,warnings = validate_html_w3c(html_code)
    return jsonify({"Errors": errors, "Warnings": warnings})