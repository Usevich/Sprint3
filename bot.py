import telebot
from PIL import Image, ImageOps
import io
from telebot import types
import os

TOKEN_FILE = "teletoken.txt"


def read_token_from_file(filename):
    """
    Читает токен Telegram из указанного файла.

    :param filename: Имя файла токена.
    :return: Строка токена.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Файл токена '{filename}' не найден. Убедитесь, что он существует!")

    with open(filename, "r") as f:
        token = f.read().strip()  # Читаем токен и удаляем лишние пробелы/переводы строк
    if not token:
        raise ValueError(f"Файл '{filename}' пуст. Убедитесь, что токен записан в файл.")
    return token


# Считываем токен из файла
TOKEN = read_token_from_file(TOKEN_FILE)

bot = telebot.TeleBot(TOKEN)

user_states = {}  # тут будем хранить информацию о действиях пользователя

# набор символов из которых составляем изображение
ASCII_CHARS = '@%#*+=-:. '


def resize_image(image, new_width=100):
    """
    Изменяет размер изображения, сохраняя соотношение сторон.

    :param image: Исходное изображение (PIL.Image).
    :param new_width: Новая ширина изображения.
    :return: Изображение с измененным размером (PIL.Image).
    """
    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))


def grayify(image):
    """
    Преобразует изображение в оттенки серого.

    :param image: Исходное изображение (PIL.Image).
    :return: Изображение в оттенках серого (PIL.Image).
    """
    return image.convert("L")


def image_to_ascii(image_stream, new_width=40, ascii_chars=ASCII_CHARS):
    """
    Преобразует изображение в ASCII-арт.

    :param image_stream: Поток байтов изображения.
    :param new_width: Ширина ASCII-арта (количество символов в строке).
    :param ascii_chars: Набор символов для создания ASCII-арта.
    :return: Строка, содержащая ASCII-арт.
    """
    # Переводим в оттенки серого
    image = Image.open(image_stream).convert('L')

    # меняем размер сохраняя отношение сторон
    width, height = image.size
    aspect_ratio = height / float(width)
    new_height = int(
        aspect_ratio * new_width * 0.55)  # 0,55 так как буквы выше чем шире
    img_resized = image.resize((new_width, new_height))

    img_str = pixels_to_ascii(img_resized, ascii_chars)
    img_width = img_resized.width

    max_characters = 4000 - (new_width + 1)
    max_rows = max_characters // (new_width + 1)

    ascii_art = ""
    for i in range(0, min(max_rows * img_width, len(img_str)), img_width):
        ascii_art += img_str[i:i + img_width] + "\n"

    return ascii_art


def pixels_to_ascii(image, ascii_chars):
    """
    Преобразует пиксели изображения в символы ASCII.

    :param image: Изображение в оттенках серого (PIL.Image).
    :param ascii_chars: Набор символов для преобразования.
    :return: Строка символов, представляющая изображение.
    """
    pixels = image.getdata()
    characters = ""
    for pixel in pixels:
        characters += ascii_chars[pixel * len(ascii_chars) // 256]
    return characters


# Огрубляем изображение
def pixelate_image(image, pixel_size):
    """
    Огрубляет изображение, создавая эффект пикселизации.

    :param image: Исходное изображение (PIL.Image).
    :param pixel_size: Размер пикселя для огрубления.
    :return: Пикселизированное изображение (PIL.Image).
    """
    image = image.resize(
        (image.size[0] // pixel_size, image.size[1] // pixel_size),
        Image.NEAREST
    )
    image = image.resize(
        (image.size[0] * pixel_size, image.size[1] * pixel_size),
        Image.NEAREST
    )
    return image


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Обрабатывает команды /start и /help. Отправляет приветственное сообщение.

    :param message: Объект сообщения от пользователя.
    """
    bot.reply_to(message, "Send me an image, and I'll provide options for you!")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """
    Обрабатывает получение фотографии от пользователя. Предлагает варианты действий.

    :param message: Объект сообщения с фотографией.
    """
    bot.reply_to(message, "I got your photo! Please choose what you'd like to do with it.",
                 reply_markup=get_options_keyboard())
    user_states[message.chat.id] = {'photo': message.photo[-1].file_id}


def get_options_keyboard():
    """
    Создает клавиатуру с вариантами действий для пользователя.

    :return: Объект InlineKeyboardMarkup с кнопками.
    """
    keyboard = types.InlineKeyboardMarkup()
    pixelate_btn = types.InlineKeyboardButton("Pixelate", callback_data="pixelate")
    ascii_btn = types.InlineKeyboardButton("ASCII Art", callback_data="ascii")
    invert_btn = types.InlineKeyboardButton("Invert Colors", callback_data="invert")
    horizontal_mirror_btn = types.InlineKeyboardButton("Mirror Horizontally", callback_data="mirror_horizontal")
    vertical_mirror_btn = types.InlineKeyboardButton("Mirror Vertically", callback_data="mirror_vertical")
    heatmap_btn = types.InlineKeyboardButton("Heatmap", callback_data="heatmap")
    keyboard.add(pixelate_btn, ascii_btn, invert_btn)
    keyboard.add(horizontal_mirror_btn, vertical_mirror_btn)
    keyboard.add(heatmap_btn)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """
    Обрабатывает нажатие на кнопки встроенной клавиатуры.

    :param call: Объект callback-запроса.
    """
    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Pixelating your image...")
        pixelate_and_send(call.message)
    elif call.data == "ascii":
        bot.answer_callback_query(call.id, "Please send me the characters you want to use for ASCII art.")
        user_states[call.message.chat.id]['waiting_for_chars'] = True
    elif call.data == "invert":  # Обработка нажатия кнопки "Invert Colors"
        bot.answer_callback_query(call.id, "Inverting colors of your image...")
        invert_and_send(call.message)
    elif call.data == "mirror_horizontal":
        bot.answer_callback_query(call.id, "Reflecting your image horizontally...")
        mirror_and_send(call.message, direction="horizontal")
    elif call.data == "mirror_vertical":
        bot.answer_callback_query(call.id, "Reflecting your image vertically...")
        mirror_and_send(call.message, direction="vertical")
    elif call.data == "heatmap":  # Новый случай для тепловой карты
        bot.answer_callback_query(call.id, "Converting your image to a heatmap...")
        heatmap_and_send(call.message)


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('waiting_for_chars', False))
def handle_ascii_chars(message):
    """
    Обрабатывает ввод пользовательского набора символов для ASCII-арта.

    :param message: Объект сообщения с набором символов.
    """
    user_states[message.chat.id]['ascii_chars'] = message.text
    user_states[message.chat.id]['waiting_for_chars'] = False
    ascii_and_send(message)


def pixelate_and_send(message):
    """
    Пикселизирует изображение и отправляет его пользователю.

    :param message: Объект сообщения, содержащий идентификатор фотографии.
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    pixelated = pixelate_image(image, 20)

    output_stream = io.BytesIO()
    pixelated.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


def ascii_and_send(message):
    """
    Преобразует изображение в ASCII-арт и отправляет его пользователю.

    :param message: Объект сообщения, содержащий идентификатор фотографии.
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    ascii_chars = user_states[message.chat.id].get('ascii_chars', ASCII_CHARS)
    ascii_art = image_to_ascii(image_stream, ascii_chars=ascii_chars)
    bot.send_message(message.chat.id, f"```\n{ascii_art}\n```", parse_mode="MarkdownV2")

def invert_colors(image):
    """
    Инвертирует цвета изображения.

    :param image: Исходное изображение (PIL.Image).
    :return: Изображение с инвертированными цветами (PIL.Image).
    """
    if image.mode == 'RGBA':
        # Для прозрачных изображений обработка немного отличается
        r, g, b, a = image.split()
        rgb_image = Image.merge("RGB", (r, g, b))
        inverted = ImageOps.invert(rgb_image)
        r, g, b = inverted.split()
        return Image.merge("RGBA", (r, g, b, a))
    elif image.mode == 'RGB':
        return ImageOps.invert(image)
    else:
        raise ValueError("Unsupported image mode for inversion!")  # Обработка других режимов изображения

def invert_and_send(message):
    """
    Инвертирует цвета изображения и отправляет пользователю.

    :param message: Объект сообщения, содержащий идентификатор фотографии.
    """
    photo_id = user_states[message.chat.id]['photo']  # Получаем ID фото
    file_info = bot.get_file(photo_id)  # Запрашиваем информацию о файле
    downloaded_file = bot.download_file(file_info.file_path)  # Скачиваем изображение

    # Открываем изображение как поток байтов
    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)

    # Инвертируем изображение с помощью нашей функции invert_colors
    inverted_image = invert_colors(image)

    # Сохраняем результат в поток байтов
    output_stream = io.BytesIO()
    inverted_image.save(output_stream, format="JPEG")
    output_stream.seek(0)

    # Отправляем инвертированное изображение обратно пользователю
    bot.send_photo(message.chat.id, output_stream)

def mirror_image(image, direction="horizontal"):
    """
    Создает отражение изображения.

    :param image: Исходное изображение (PIL.Image).
    :param direction: Направление: 'horizontal' или 'vertical'.
    :return: Отраженное изображение (PIL.Image).
    """
    if direction == "horizontal":
        return image.transpose(Image.FLIP_LEFT_RIGHT)
    elif direction == "vertical":
        return image.transpose(Image.FLIP_TOP_BOTTOM)
    else:
        raise ValueError("Invalid direction! Use 'horizontal' or 'vertical'.")


def mirror_and_send(message, direction):
    """
    Отражает изображение и отправляет пользователю.

    :param message: Объект сообщения, содержащий идентификатор фотографии.
    :param direction: Направление: 'horizontal' или 'vertical'.
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)

    # Отражаем изображение
    mirrored_image = mirror_image(image, direction)

    # Сохраняем результат в поток байтов
    output_stream = io.BytesIO()
    mirrored_image.save(output_stream, format="JPEG")
    output_stream.seek(0)

    # Отправляем отражённое изображение
    bot.send_photo(message.chat.id, output_stream)


def convert_to_heatmap(image):
    """
    Преобразовывает изображение в тепловую карту.

    :param image: Исходное изображение (PIL.Image).
    :return: Изображение в виде тепловой карты (PIL.Image).
    """
    # Преобразуем изображение в оттенки серого
    grayscale = image.convert("L")

    # Применяем цветовую карту через ImageOps.colorize
    # Синий для холодных областей, оранжевый для теплых
    heatmap = ImageOps.colorize(
        grayscale,
        black="blue",  # Цвет для "темных" (холодных) областей
        white="red"  # Цвет для "светлых" (теплых) областей
    )
    return heatmap

def heatmap_and_send(message):
    """
    Преобразовывает изображение в тепловую карту и отправляет его пользователю.

    :param message: Объект сообщения, содержащий идентификатор фотографии.
    """
    photo_id = user_states[message.chat.id]['photo']  # Получаем ID фото
    file_info = bot.get_file(photo_id)  # Запрашиваем информацию о файле
    downloaded_file = bot.download_file(file_info.file_path)  # Скачиваем изображение

    # Открываем изображение как поток байтов
    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)

    # Применяем тепловую карту через нашу функцию
    heatmap_image = convert_to_heatmap(image)

    # Сохраняем результат в поток байтов
    output_stream = io.BytesIO()
    heatmap_image.save(output_stream, format="JPEG")
    output_stream.seek(0)

    # Отправляем изображение тепловой карты обратно пользователю
    bot.send_photo(message.chat.id, output_stream)



bot.polling(none_stop=True)