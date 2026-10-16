from flask import Flask
import threading
import os

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot encendido!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

def init_db():
    conn = sqlite3.connect("registros.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS recaudacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, tipo TEXT, monto REAL, usuario TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS combustible (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, tipo_combustible TEXT, litros REAL, monto REAL, usuario TEXT
    )""")
    conn.commit()
    conn.close()
init_db()

def menu_principal():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Registrar Recaudación 💰", callback_data="menu_recaudar"),
        InlineKeyboardButton("Carga de Combustible ⛽", callback_data="menu_combustible"),
        InlineKeyboardButton("Generar Reportes 🧾", callback_data="menu_reportes")
    )
    return markup

def menu_tipos_recaudacion():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Efectivo", callback_data="tipo_Efectivo"),
        InlineKeyboardButton("Tarjeta", callback_data="tipo_Tarjeta"),
        InlineKeyboardButton("Campañas", callback_data="tipo_Campañas"),
        InlineKeyboardButton("Créditos", callback_data="tipo_Créditos"),
        InlineKeyboardButton("Promociones", callback_data="tipo_Promociones"),
        InlineKeyboardButton("⬅️ Volver", callback_data="volver_inicio")
    )
    return markup

user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Hola {message.from_user.first_name} 👋\n¿Que querés hacer hoy?", reply_markup=menu_principal())

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    chat_id = call.message.chat.id
    if call.data == "volver_inicio":
        bot.edit_message_text("¿Que querés hacer hoy?", chat_id, call.message.message_id, reply_markup=menu_principal())
    elif call.data == "menu_recaudar":
        bot.edit_message_text("Seleccioná el tipo de ingreso:", chat_id, call.message.message_id, reply_markup=menu_tipos_recaudacion())
    elif call.data.startswith("tipo_"):
        tipo = call.data.replace("tipo_", "")
        user_state[chat_id] = {"tipo": tipo, "esperando": "monto_recaudacion"}
        bot.send_message(chat_id, f"{tipo}. 💰\n¿Cuánto fue? Ej: 150000")
    elif call.data == "menu_combustible":
        user_state[chat_id] = {"esperando": "combustible_datos"}
        bot.send_message(chat_id, "⛽ Escribí: TIPO LITROS MONTO\nEj: Nafta 20 150000")
    elif call.data == "menu_reportes":
        generar_reporte(chat_id)

def generar_reporte(chat_id):
    conn = sqlite3.connect("registros.db")
    c = conn.cursor()
    hoy = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT tipo, SUM(monto) FROM recaudacion WHERE fecha LIKE? GROUP BY tipo", (f"{hoy}%",))
    rec = c.fetchall()
    c.execute("SELECT SUM(litros), SUM(monto) FROM combustible WHERE fecha LIKE?", (f"{hoy}%",))
    comb = c.fetchone()
    conn.close()
    texto = f"🧾 REPORTE HOY - {hoy}\n\n"
    total = 0
    if rec:
        texto += "💰 RECAUDACIÓN:\n"
        for tipo, suma in rec:
            texto += f" - {tipo}: Gs. {suma:,.0f}\n"; total += suma
        texto += f"\nTOTAL: Gs. {total:,.0f}\n"
    texto += f"\n⛽ COMBUSTIBLE: {comb[0] or 0}L - Gs. {comb[1] or 0:,.0f}"
    bot.send_message(chat_id, texto, reply_markup=menu_principal())

@bot.message_handler(func=lambda m: True)
def recibir(message):
    chat_id = message.chat.id
    if chat_id not in user_state: return
    estado = user_state[chat_id]
    if estado.get("esperando") == "monto_recaudacion":
        try:
            monto = float(message.text.replace(".","").replace(",","").replace("Gs","").strip())
            conn = sqlite3.connect("registros.db"); c = conn.cursor()
            c.execute("INSERT INTO recaudacion (fecha,tipo,monto,usuario) VALUES (?,?,?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), estado["tipo"], monto, message.from_user.first_name))
            conn.commit(); conn.close(); user_state.pop(chat_id)
            bot.send_message(chat_id, f"✅ Guardado: {estado['tipo']} - Gs. {monto:,.0f}", reply_markup=menu_principal())
        except: bot.send_message(chat_id, "⚠️ Mandá solo números. Ej: 150000")
    elif estado.get("esperando") == "combustible_datos":
        try:
            p = message.text.split(); tipo_c, litros, monto = p[0], float(p[1]), float(p[2].replace(".","").replace(",",""))
            conn = sqlite3.connect("registros.db"); c = conn.cursor()
            c.execute("INSERT INTO combustible (fecha,tipo_combustible,litros,monto,usuario) VALUES (?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M"), tipo_c, litros, monto, message.from_user.first_name))
            conn.commit(); conn.close(); user_state.pop(chat_id)
            bot.send_message(chat_id, f"✅ Carga: {tipo_c} {litros}L - Gs. {monto:,.0f}", reply_markup=menu_principal())
        except: bot.send_message(chat_id, "⚠️ Usá: TIPO LITROS MONTO\nEj: Nafta 20 150000")

bot.infinity_polling()