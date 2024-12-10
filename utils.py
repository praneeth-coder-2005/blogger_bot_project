import asyncio
import logging
import telebot

from utils import (
    get_current_time,
    get_current_date,
    get_movie_details,
    get_movie_rating,
    search_movies,
    process_url_upload,
    process_rename,
    process_file_upload,
)
from config import BOT_TOKEN, API_ID, API_HASH  # Import from config.py

# --- Logging ---
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Bot Initialization ---
bot = telebot.TeleBot(BOT_TOKEN)

# --- Pyrogram Client Initialization ---
from pyrogram import Client, filters  # Import pyrogram here

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# --- Global Variables ---
user_data = {}  # To store user-specific data during file upload


# --- Command Handlers ---
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """Sends a welcome message with inline buttons."""
    try:
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("Time", callback_data="time"),
            telebot.types.InlineKeyboardButton("Date", callback_data="date"),
            telebot.types.InlineKeyboardButton("Movie Details", callback_data="movie_details"),
            telebot.types.InlineKeyboardButton("Movie Ratings", callback_data="movie_ratings"),
            telebot.types.InlineKeyboardButton("URL Upload", callback_data="url_upload"),
        )
        bot.reply_to(
            message, "Hello! I'm a helpful bot. Choose an option:", reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Error in send_welcome: {e}")
        bot.reply_to(
            message, "Oops! Something went wrong. Please try again later."
        )


# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """Handles inline button callbacks."""
    try:
        if call.data == "time":
            bot.answer_callback_query(
                call.id, text=f"Current time: {get_current_time()}"
            )
        elif call.data == "date":
            bot.answer_callback_query(
                call.id, text=f"Today's date: {get_current_date()}"
            )
        elif call.data == "movie_details":
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id, "Send me a movie title to get details"
            )
            bot.register_next_step_handler(call.message, process_movie_request)
        elif call.data == "movie_ratings":
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id, "Send me a movie title to get ratings"
            )
            bot.register_next_step_handler(call.message, process_movie_rating_request)
        elif call.data == "url_upload":
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "Send me the URL of the file you want to upload:",
            )
            bot.register_next_step_handler(call.message, lambda msg: process_url_upload(msg, bot, app))  # Pass bot and app to process_url_upload
        elif call.data == "rename":
            bot.answer_callback_query(call.id)
            message = call.message
            bot.send_message(
                message.chat.id, "Enter a new file name (without extension):"
            )
            bot.register_next_step_handler(message, lambda msg: process_rename(msg, bot, app))  # Pass bot and app to process_rename
        elif call.data == "default" or call.data == "cancel":
            bot.answer_callback_query(call.id)
            message = call.message
            process_file_upload(
                message, custom_file_name=None, bot=bot, app=app
            )  # Use default name if "default" is clicked, pass bot and app here as well
        else:  # Handle movie selection callbacks
            bot.answer_callback_query(call.id)
            movie_name = call.data
            movie_info = get_movie_details(movie_name)
            bot.send_message(call.message.chat.id, movie_info, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in callback_query: {e}")
        bot.send_message(
            call.message.chat.id, "Oops! Something went wrong. Please try again later."
        )


# --- Message Handlers ---
def process_movie_request(message):
    """Processes the movie title and sends movie details or shows options."""
    try:
        movie_name = message.text
        movies = search_movies(movie_name)

        if movies is None:
            bot.send_message(
                message.chat.id, "Movie search failed. Please try again later."
            )
            return

        if len(movies) == 1:
            movie_info = get_movie_details(movies[0]["Title"])
            bot.send_message(message.chat.id, movie_info, parse_mode="Markdown")
        elif len(movies) > 1:
            markup = telebot.types.InlineKeyboardMarkup()
            for movie in movies:
                title = movie["Title"]
                year = movie["Year"]
                markup.add(
                    telebot.types.InlineKeyboardButton(
                        f"{title} ({year})", callback_data=title
                    )
                )
            bot.send_message(
                message.chat.id, "Select the correct movie:", reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "Movie not found.")

    except Exception as e:
        logger.error(f"Error in process_movie_request: {e}")
        bot.send_message(
            message.chat.id, "Oops! Something went wrong. Please try again later."
        )


def process_movie_rating_request(message):
    """Processes the movie title and sends movie ratings."""
    try:
        movie_name = message.text
        movie_ratings = get_movie_rating(movie_name)
        bot.send_message(message.chat.id, movie_ratings)
    except Exception as e:
        logger.error(f"Error in process_movie_rating_request: {e}")
        bot.send_message(
            message.chat.id, "Oops! Something went wrong. Please try again later."
        )


# --- Pyrogram Handler for File Upload ---
@app.on_message(filters.command("upload") & filters.private)
async def upload_file(client, message):
    try:
        # Get file path or URL from the user
        file_path_or_url = message.text.split(" ", 1)[1]

        # Send a message to the user to indicate the upload is starting
        await app.send_message(message.chat.id, "Starting file upload...")

        await app.send_document(
            chat_id=message.chat.id,
            document=file_path_or_url,  # Or pass a file-like object
            caption="Uploaded file",
            progress=progress_callback,  # Optional progress callback function
        )
    except Exception as e:
        print(f"Error uploading file: {e}")
        await app.send_message(message.chat.id, f"Error uploading file: {e}")

async def progress_callback(current, total):
    print(f"{current * 100 / total:.1f}%")

# --- Start the Bots ---
async def main():
    """Starts both telebot and Pyrogram clients."""
    await app.start()  # Start Pyrogram client
    bot.infinity_polling()
    await app.stop()  # Stop Pyrogram client when telebot finishes

if __name__ == "__main__":
    asyncio.run(main())
            
