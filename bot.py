import os
import nest_asyncio
nest_asyncio.apply()  

from PIL import Image
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
import reeder  

# УБРАТЬ ФОН
def remove_background(input_path, output_path, threshold=240):
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()
    newData = []
    for item in datas:
        if item[0] >= threshold and item[1] >= threshold and item[2] >= threshold:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)
    img.putdata(newData)
    img.save(output_path, "PNG")

NAME, SIGNATURE, DOCUMENT = range(3)

# /START 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Welcome to the document signing bot!\n\n"
        "Use the /doc command to start the signing process."
    )
    await update.message.reply_text(welcome_text)

# /DOC
async def start_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please send your full name.")
    return NAME

# ФИО Input
async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_name = update.message.text
    context.user_data["name"] = user_name
    await update.message.reply_text("Thank you! Now please send an image of your signature (as a picture).")
    return SIGNATURE

# Подпись Input
async def received_signature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    user_signature_path = "user_signature.png"
    await photo_file.download_to_drive(user_signature_path)

    processed_signature_path = "processed_signature.png"
    remove_background(user_signature_path, processed_signature_path)
    # Save processed signature path for later use
    context.user_data["processed_signature"] = processed_signature_path

    await update.message.reply_text("Now please send the PDF document you want to sign.")
    return DOCUMENT

# PDF Input
async def received_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    document = update.message.document
    if not document:
        await update.message.reply_text("Please send a valid PDF document.")
        return DOCUMENT

    file = await document.get_file()
    document_path = "document_to_sign.pdf"
    await file.download_to_drive(document_path)

    user_name = context.user_data.get("name", "Unknown")
    processed_signature = context.user_data.get("processed_signature")
    if not processed_signature:
        await update.message.reply_text("Signature processing error.")
        return ConversationHandler.END

    signed_pdf_path = "signed_document.pdf"
    reeder.sign_pdf(document_path, processed_signature, user_name, signed_pdf_path)

    await update.message.reply_text("Here is your signed document:")
    await update.message.reply_document(document=open(signed_pdf_path, "rb"))

    # УБОРКА ФАЙЛОВ
    os.remove("user_signature.png")
    os.remove(processed_signature)
    os.remove(document_path)
    os.remove(signed_pdf_path)

    return ConversationHandler.END

# /CANCEL 
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def main():
    application = ApplicationBuilder().token("TELEGRAM_BOT_API").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("doc", start_doc)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)],
            SIGNATURE: [MessageHandler(filters.PHOTO, received_signature)],
            DOCUMENT: [MessageHandler(filters.Document.MimeType("application/pdf"), received_document)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
