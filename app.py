from flask import Flask, render_template, request, flash
from flask_cors import CORS, cross_origin
import requests
from bs4 import BeautifulSoup as bs
from urllib.request import urlopen as uReq
import logging
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    filename="scrapper.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
CORS(app)
# Required for flash messages
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# MongoDB configuration
MONGODB_URI = os.getenv(
    'MONGODB_URI', 'mongodb+srv://2022csravina12304:221004@cluster0.kixryvt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')


@app.route("/", methods=['GET'])
def homepage():
    return render_template("index.html")


@app.route("/review", methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        try:
            searchString = request.form['content'].replace(" ", "")
            if not searchString:
                flash('Please enter a search term')
                return render_template('index.html')

            flipkart_url = "https://www.flipkart.com/search?q=" + searchString
            logging.info(f"Searching for: {searchString}")

            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # Add delay to avoid rate limiting
            time.sleep(1)

            uClient = uReq(flipkart_url)
            flipkartPage = uClient.read()
            uClient.close()

            flipkart_html = bs(flipkartPage, "html.parser")
            bigboxes = flipkart_html.find_all("div", {"class": "_75nlfW"})

            if len(bigboxes) <= 3:
                logging.warning(
                    f"Not enough product boxes found. Length: {len(bigboxes)}")
                flash('No products found or page layout has changed.')
                return render_template('index.html')

            del bigboxes[0:3]

            if not bigboxes:
                logging.warning(
                    "No product box found after deleting first 3 items.")
                flash('No products found. Try another search keyword.')
                return render_template('index.html')

            box = bigboxes[1]

            productLink = "https://www.flipkart.com" + box.div.div.a['href']
            prodRes = requests.get(productLink, headers=headers)
            prodRes.encoding = 'utf-8'
            prod_html = bs(prodRes.text, "html.parser")

            commentboxes = prod_html.find_all('div', {'class': "RcXBOT"})

            if not commentboxes:
                logging.warning("No reviews found for the product.")
                flash('No reviews found for this product.')
                return render_template('index.html')

            filename = searchString + ".csv"
            with open(filename, "w", encoding='utf-8') as fw:
                headers = "Product, Customer Name, Rating, Heading, Comment\n"
                fw.write(headers)

                reviews = []
                for commentbox in commentboxes:
                    try:
                        name = commentbox.div.div.find_all(
                            'p', {'class': '_2NsDsF AwS1CA'})[0].text
                    except:
                        name = "No Name"
                        logging.info("Name not found")

                    try:
                        rating = commentbox.div.div.div.div.text
                    except:
                        rating = 'No Rating'
                        logging.info("Rating not found")

                    try:
                        commentHead = commentbox.div.div.div.p.text
                    except:
                        commentHead = 'No Comment Heading'
                        logging.info("Comment Head not found")

                    try:
                        comtag = commentbox.div.div.find_all(
                            'div', {'class': 'ZmyHeo'})
                        custComment = comtag[0].div.text
                    except:
                        custComment = "No Comment"
                        logging.info("Customer Comment not found")

                    mydict = {
                        "Product": searchString,
                        "Name": name,
                        "Rating": rating,
                        "CommentHead": commentHead,
                        "Comment": custComment
                    }
                    reviews.append(mydict)

                    fw.write(
                        f"{searchString}, {name}, {rating}, {commentHead}, {custComment}\n")

            logging.info(f"Successfully scraped {len(reviews)} reviews")

            # MongoDB connection with error handling
            try:
                client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
                db = client['review_scrap']
                review_col = db['review_scrap_data']
                review_col.insert_many(reviews)
                client.close()
                logging.info("Successfully saved to MongoDB")
            except Exception as e:
                logging.error(f"MongoDB Error: {str(e)}")
                # Continue even if MongoDB fails - at least we have the CSV

            return render_template('result.html', reviews=reviews)

        except Exception as e:
            logging.error(f"Exception occurred: {str(e)}", exc_info=True)
            flash('Something went wrong. Please try again.')
            return render_template('index.html')
    else:
        return render_template('index.html')


if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
