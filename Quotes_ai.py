import json
import os
import random
import re
import threading
import time
import customtkinter as ctk
import requests

# 1. CustomTkinter Configuration
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# 2. OpenRouter API Configuration
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "books_cache.json"
)

# 4 Standard Mood Options
MOOD_OPTIONS = [
    "Inspirational & Motivational",
    "Melancholic & Dark",
    "Romantic & Emotional",
    "Philosophical & Deep",
]


def load_from_cache(query):
  """Check if cached query exists locally."""
  if not os.path.exists(CACHE_FILE):
    return None
  try:
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
      cache = json.load(f)
      key = query.lower().strip()
      return cache.get(key)
  except Exception:
    return None


def get_all_saved_book_titles():
  """Extracts all book titles from local cache to display in the sidebar."""
  if not os.path.exists(CACHE_FILE):
    return []
  try:
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
      cache = json.load(f)
      titles = set()
      for key, data in cache.items():
        if key.startswith("mood:"):
          items = data if isinstance(data, list) else [data]
          for item in items:
            if isinstance(item, dict) and "book_title" in item:
              titles.add(f"✨ Mood: {key.replace('mood:', '').strip()}")
        else:
          items = data if isinstance(data, list) else [data]
          for item in items:
            if isinstance(item, dict) and "book_title" in item:
              titles.add(item["book_title"])
      return list(titles)
  except Exception:
    return []


def save_to_cache(query, data):
  """Save books & quotes locally (keeps up to 5 diverse entries per query)."""
  cache = {}
  if os.path.exists(CACHE_FILE):
    try:
      with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)
    except Exception:
      cache = {}

  key = query.lower().strip()

  if key not in cache:
    cache[key] = []

  if isinstance(cache[key], list):
    if data not in cache[key]:
      cache[key].insert(0, data)
      cache[key] = cache[key][:5]
  else:
    cache[key] = [data, cache[key]]

  try:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
      json.dump(cache, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"Error saving cache: {e}")


def fetch_book_text(query, status_callback):
  status_callback(f"🔍 Searching Project Gutenberg for '{query}'...")
  search_url = (
      f"https://gutendex.com/books?search={requests.utils.quote(query)}"
  )
  headers = {"User-Agent": "GutenbergQuoteGenerator/1.0"}

  try:
    #  Timeout
    response = requests.get(search_url, headers=headers, timeout=8)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])

    if not results:
      status_callback(f" No books found for '{query}'.")
      return None, None, None

    book = random.choice(results[:3]) if len(results) >= 3 else results[0]
    book_title = book.get("title", "Unknown Title")
    authors = book.get("authors", [])
    author_name = authors[0].get("name", "Unknown Author") if authors else "Unknown"

    formats = book.get("formats", {})
    txt_url = None
    for fmt, url_link in formats.items():
      if "text/plain" in fmt and url_link.endswith(".txt"):
        txt_url = url_link
        break

    if not txt_url:
      for fmt, url_link in formats.items():
        if "text/plain" in fmt:
          txt_url = url_link
          break

    if not txt_url:
      status_callback(" No plain text format available.")
      return book_title, author_name, None

    status_callback(f"📖 Downloading: {book_title[:30]}...")
    # Timeout
    text_response = requests.get(txt_url, headers=headers, timeout=10)
    text_response.raise_for_status()

    return book_title, author_name, text_response.text
  except Exception:
    return None, None, None


def chunk_text(full_text):
  paragraphs = [
      p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 80
  ]
  total_p = len(paragraphs)
  if total_p < 15:
    return "\n\n".join(paragraphs)

  r1 = random.randint(0, max(0, int(total_p * 0.2)))
  r2 = random.randint(
      int(total_p * 0.3), max(int(total_p * 0.3), int(total_p * 0.5))
  )
  r3 = random.randint(
      int(total_p * 0.6), max(int(total_p * 0.6), int(total_p * 0.8))
  )

  p1 = paragraphs[r1 : r1 + 4]
  p2 = paragraphs[r2 : r2 + 4]
  p3 = paragraphs[r3 : r3 + 4]

  return "\n\n".join(p1 + p2 + p3)


def suggest_book_for_mood(mood, status_callback):
  status_callback(f"✨ Finding a new book matching '{mood}'...")

  prompt = (
      f"Suggest ONE famous classic book available on Project Gutenberg that"
      f" strongly fits the mood: '{mood}'.\nRespond ONLY with the exact title of"
      " the book. Do NOT add quotation marks, explanations, or author name."
  )

  headers = {
      "Authorization": f"Bearer {API_KEY}",
      "Content-Type": "application/json",
  }

  payload = {
      "model": "nvidia/nemotron-3.5-lightning:free",
      "messages": [{"role": "user", "content": prompt}],
  }

  try:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=6,
    )
    if response.status_code == 200:
      res_data = response.json()
      book_name = (
          res_data["choices"][0]["message"]["content"]
          .strip()
          .replace('"', "")
          .replace("'", "")
      )
      return book_name
  except Exception:
    pass

  defaults = {
      "Inspirational & Motivational": [
          "Walden",
          "Meditations",
          "Self-Reliance",
      ],
      "Melancholic & Dark": ["Frankenstein", "Dracula", "The Fall of the House of Usher"],
      "Romantic & Emotional": ["Pride and Prejudice", "Jane Eyre", "Wuthering Heights"],
      "Philosophical & Deep": ["Metamorphosis", "Beyond Good and Evil", "Thus Spoke Zarathustra"],
  }
  options = defaults.get(mood, ["Frankenstein"])
  return random.choice(options)


def extract_quotes_from_chunks(
    book_title, chunks_text, status_callback, mood=None
):
  mood_instruction = (
      f"Specifically choose distinct, fresh quotes that match the mood:"
      f" '{mood}'."
      if mood
      else ""
  )

  prompt = (
      f"You are a master literary expert. Below are extracts from the book"
      f" '{book_title}'.\nExtract 3 UNIQUE, powerful, and memorable direct"
      f" quotes from this book. {mood_instruction}\n\nSTRICT"
      " INSTRUCTIONS:\nOutput ONLY the 3 quotes formatted as a numbered"
      " list.\nAbsolutely NO introduction, NO commentary, NO"
      " explanations.\nFormat:\n1. 'First quote'\n2. 'Second quote'\n3. 'Third"
      f" quote'\n\nBook Extracts:\n{chunks_text[:3000]}"
  )

  status_callback("⚡ AI Extracting 3 Best Quotes...")

  headers = {
      "Authorization": f"Bearer {API_KEY}",
      "Content-Type": "application/json",
      "HTTP-Referer": "https://github.com/gutenberg-quote-generator",
      "X-Title": "Gutenberg Quote Generator",
  }

  payload = {
      "model": "nvidia/nemotron-3.5-lightning:free",
      "messages": [{"role": "user", "content": prompt}],
  }

  try:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=6,
    )
    if response.status_code == 200:
      res_data = response.json()
      return res_data["choices"][0]["message"]["content"].strip()
  except Exception:
    pass

  return None


# --- 3D COLD BLUE & WARM YELLOW UI CLASS WITH SIDEBAR ---
class QuoteGeneratorApp(ctk.CTk):

  def __init__(self):
    super().__init__()

    # Cold Blue background with Warm Yellow & Blue Accent Palette
    self.COLOR_BG = "#E2EDF8"        # Soft Cold Sky Blue Background
    self.COLOR_CARD = "#FFF9E6"      # Warm Yellow / Gold Tint Card
    self.COLOR_SIDEBAR = "#D4E3F3"   # Sidebar Background
    self.COLOR_ACCENT = "#2D68C4"    # Main Cold Blue
    self.COLOR_YELLOW = "#FFC107"    # Warm Hame9 Yellow
    self.COLOR_HOVER = "#1F4E9E"     # Darker Blue Hover
    self.COLOR_TEXT = "#2C3E50"      # Dark Slate Text
    self.COLOR_MUTED = "#64748B"     # Soft Gray-Blue

    self.title("Gutenberg Quote Generator • 3D Edition")
    self.geometry("980x720")
    self.configure(fg_color=self.COLOR_BG)
    self.resizable(False, False)

    self.quotes_list = []
    self.current_quote_index = 0
    self.book_title = ""
    self.author_name = ""

    # --- LEFT SIDEBAR (Saved Books Cache) ---
    self.sidebar_frame = ctk.CTkFrame(
        self,
        width=250,
        corner_radius=0,
        fg_color=self.COLOR_SIDEBAR,
        border_width=2,
        border_color=self.COLOR_YELLOW,
    )
    self.sidebar_frame.pack(side="left", fill="y")
    self.sidebar_frame.pack_propagate(False)

    self.sidebar_title = ctk.CTkLabel(
        self.sidebar_frame,
        text="📚 SAVED CACHE",
        font=ctk.CTkFont(size=14, weight="bold"),
        text_color=self.COLOR_ACCENT,
    )
    self.sidebar_title.pack(pady=(20, 10))

    self.sidebar_scroll = ctk.CTkScrollableFrame(
        self.sidebar_frame,
        width=220,
        height=540,
        fg_color="transparent",
        scrollbar_button_color=self.COLOR_YELLOW,
        scrollbar_button_hover_color=self.COLOR_ACCENT,
    )
    self.sidebar_scroll.pack(padx=10, pady=5, fill="both", expand=True)

    # --- RIGHT MAIN CONTENT AREA ---
    self.main_content = ctk.CTkFrame(self, fg_color="transparent")
    self.main_content.pack(side="right", fill="both", expand=True, padx=15, pady=10)

    # Header Section
    self.header_frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
    self.header_frame.pack(pady=(10, 5))

    self.title_label = ctk.CTkLabel(
        self.header_frame,
        text="✨ GUTENBERG QUOTE GENERATOR",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=self.COLOR_ACCENT,
    )
    self.title_label.pack()

    self.subtitle_label = ctk.CTkLabel(
        self.header_frame,
        text="Discover timeless wisdom from classical literature",
        font=ctk.CTkFont(size=12),
        text_color=self.COLOR_MUTED,
    )
    self.subtitle_label.pack(pady=(2, 0))

    # Styled Tabview
    self.tabview = ctk.CTkTabview(
        self.main_content,
        width=670,
        height=165,
        fg_color=self.COLOR_CARD,
        corner_radius=16,
        border_width=2,
        border_color=self.COLOR_YELLOW,
        segmented_button_fg_color="#CBD5E1",
        segmented_button_selected_color=self.COLOR_ACCENT,
        segmented_button_selected_hover_color=self.COLOR_HOVER,
        segmented_button_unselected_color="#E2E8F0",
        segmented_button_unselected_hover_color="#94A3B8",
        text_color="#FFFFFF",
    )
    self.tabview.pack(pady=8)

    self.tab_title = self.tabview.add("  Search by Title  ")
    self.tab_mood = self.tabview.add("  Search by Mood  ")

    # TAB 1: Title Search
    self.entry = ctk.CTkEntry(
        self.tab_title,
        placeholder_text="Enter book title (e.g. Frankenstein, Dracula)...",
        width=450,
        height=40,
        corner_radius=12,
        fg_color=self.COLOR_YELLOW,
        border_color=self.COLOR_ACCENT,
        border_width=1,
        text_color="#000000",
        placeholder_text_color="#4A4A4A",
    )
    self.entry.pack(pady=(10, 8))

    self.btn_search_title = ctk.CTkButton(
        self.tab_title,
        text="SEARCH BOOK",
        width=180,
        height=36,
        corner_radius=12,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=self.COLOR_ACCENT,
        hover_color=self.COLOR_HOVER,
        text_color="#FFFFFF",
        command=lambda: self.start_process(mode="title"),
    )
    self.btn_search_title.pack(pady=4)

    # TAB 2: Mood Search
    self.mood_label = ctk.CTkLabel(
        self.tab_mood,
        text="Choose your reading vibe:",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=self.COLOR_MUTED,
    )
    self.mood_label.pack(pady=(4, 4))

    self.mood_dropdown = ctk.CTkOptionMenu(
        self.tab_mood,
        values=MOOD_OPTIONS,
        width=340,
        height=36,
        corner_radius=12,
        fg_color=self.COLOR_YELLOW,
        button_color=self.COLOR_ACCENT,
        button_hover_color=self.COLOR_HOVER,
        text_color="#000000",
        dropdown_fg_color=self.COLOR_YELLOW,
        dropdown_hover_color="#FFE082",
        dropdown_text_color="#000000",
    )
    self.mood_dropdown.pack(pady=4)

    self.btn_search_mood = ctk.CTkButton(
        self.tab_mood,
        text="DISCOVER MOOD",
        width=180,
        height=36,
        corner_radius=12,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=self.COLOR_ACCENT,
        hover_color=self.COLOR_HOVER,
        text_color="#FFFFFF",
        command=lambda: self.start_process(mode="mood"),
    )
    self.btn_search_mood.pack(pady=6)

    # Status Indicator
    self.status_label = ctk.CTkLabel(
        self.main_content,
        text="",
        font=ctk.CTkFont(size=12, slant="italic"),
        text_color=self.COLOR_ACCENT,
        wraplength=600,
    )
    self.status_label.pack(pady=2)

    # Main Card Container
    self.card_frame = ctk.CTkFrame(
        self.main_content,
        width=670,
        height=240,
        corner_radius=20,
        border_width=2,
        border_color=self.COLOR_YELLOW,
        fg_color=self.COLOR_CARD,
    )
    self.card_frame.pack(pady=6)
    self.card_frame.pack_propagate(False)

    self.quote_label = ctk.CTkLabel(
        self.card_frame,
        text="Select a title or mood above to generate quotes...",
        font=ctk.CTkFont(size=15, weight="bold", slant="italic"),
        wraplength=600,
        justify="center",
        text_color=self.COLOR_TEXT,
    )
    self.quote_label.pack(expand=True, fill="both", padx=25, pady=(15, 5))

    self.info_label = ctk.CTkLabel(
        self.card_frame,
        text="",
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=self.COLOR_ACCENT,
        anchor="w",
        justify="left",
    )
    self.info_label.pack(side="bottom", fill="x", padx=25, pady=(0, 15))

    # Next Quote Button
    self.btn_next = ctk.CTkButton(
        self.main_content,
        text="NEXT QUOTE ➔",
        width=180,
        height=38,
        corner_radius=12,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=self.COLOR_ACCENT,
        text_color="#FFFFFF",
        hover_color=self.COLOR_HOVER,
        command=self.show_next_quote,
    )
    self.btn_next.pack_forget()

    # Initial Sidebar Load
    self.refresh_sidebar()

  def refresh_sidebar(self):
    """Refreshes the sidebar buttons from local cache."""
    for widget in self.sidebar_scroll.winfo_children():
      widget.destroy()

    titles = get_all_saved_book_titles()
    if not titles:
      lbl = ctk.CTkLabel(
          self.sidebar_scroll,
          text="No cached items yet.",
          text_color=self.COLOR_MUTED,
          font=ctk.CTkFont(size=11, slant="italic"),
      )
      lbl.pack(pady=10)
      return

    for title in titles:
      btn = ctk.CTkButton(
          self.sidebar_scroll,
          text=title,
          fg_color=self.COLOR_YELLOW,
          hover_color="#FFE082",
          text_color="#000000",
          border_width=1,
          border_color=self.COLOR_ACCENT,
          corner_radius=8,
          anchor="w",
          command=lambda t=title: self.load_from_sidebar(t),
      )
      btn.pack(fill="x", pady=4, padx=5)

  def load_from_sidebar(self, title):
    """Load selected book/mood instantly from sidebar cache."""
    clean_title = title.replace("✨ Mood: ", "").strip()
    if title.startswith("✨ Mood:"):
      cache_key = f"mood:{clean_title}".lower()
    else:
      cache_key = clean_title.lower()

    cached_data = load_from_cache(cache_key)
    if cached_data:
      if isinstance(cached_data, list) and len(cached_data) > 0:
        selected_cache = random.choice(cached_data)
      else:
        selected_cache = cached_data

      self.book_title = selected_cache.get("book_title", clean_title)
      self.author_name = selected_cache.get("author_name", "Unknown Author")
      self.quotes_list = selected_cache.get("quotes_list", [])
      self.current_quote_index = 0
      self.display_current_quote()
      self.update_status(f"⚡ Loaded '{clean_title}' instantly from cache!")

  def update_status(self, message):
    self.status_label.configure(text=message)

  def set_buttons_state(self, state):
    self.btn_search_title.configure(state=state)
    self.btn_search_mood.configure(state=state)

  def start_process(self, mode="title"):
    if mode == "title":
      query = self.entry.get().strip()
      if not query:
        self.update_status("⚠️ Please enter a book title first.")
        return
      mood = None
    else:
      mood = self.mood_dropdown.get()
      query = f"mood:{mood}"

    self.set_buttons_state("disabled")
    self.btn_next.pack_forget()
    self.quote_label.configure(text="Fetching literary treasures...")
    self.info_label.configure(text="")

    threading.Thread(
        target=self.run_backend_logic, args=(query, mood), daemon=True
    ).start()

  def parse_quotes(self, raw_text):
    quotes = []
    lines = raw_text.split("\n")
    for line in lines:
      line_str = line.strip()
      if not line_str:
        continue
      clean_q = re.sub(r"^\d+[\.\)]\s*", "", line_str).strip()
      clean_q = clean_q.strip('"').strip("'").strip("*").strip()
      if (
          len(clean_q) > 10
          and not clean_q.lower().startswith("here are")
          and not clean_q.lower().startswith("the provided")
      ):
        quotes.append(clean_q)
    return quotes[:3] if quotes else [raw_text]

  def display_current_quote(self):
    if not self.quotes_list:
      return
    quote = self.quotes_list[self.current_quote_index]
    self.quote_label.configure(text=f'"{quote}"')
    self.info_label.configure(
        text=f"📖  {self.book_title}\n✍️  {self.author_name}"
    )

    if self.current_quote_index < len(self.quotes_list) - 1:
      next_num = self.current_quote_index + 2
      self.btn_next.configure(text=f"SHOW QUOTE {next_num} ➔")
      self.btn_next.pack(pady=8)
    else:
      self.btn_next.pack_forget()

  def show_next_quote(self):
    if self.current_quote_index < len(self.quotes_list) - 1:
      self.current_quote_index += 1
      self.display_current_quote()

  def run_backend_logic(self, query, mood=None):
    is_mood = bool(mood)
    cache_key = query.lower().strip()

    try:
      search_query = query
      if is_mood:
        search_query = suggest_book_for_mood(mood, self.update_status)

      title, author, full_text = fetch_book_text(
          search_query, self.update_status
      )

      if full_text:
        extracted_chunks = chunk_text(full_text)
        raw_quotes = extract_quotes_from_chunks(
            title, extracted_chunks, self.update_status, mood=mood
        )

        if raw_quotes:
          parsed_quotes = self.parse_quotes(raw_quotes)

          self.book_title = title
          self.author_name = author
          self.quotes_list = parsed_quotes
          self.current_quote_index = 0

          new_data = {
              "book_title": title,
              "author_name": author,
              "quotes_list": parsed_quotes,
          }
          save_to_cache(cache_key, new_data)

          self.after(0, self.display_current_quote)
          self.after(0, self.refresh_sidebar)
          self.update_status("✅ Generated live from Gutenberg successfully!")
          self.set_buttons_state("normal")
          return
    except Exception:
      pass

    # Fallback to local cache if network times out or fails
    cached_data = load_from_cache(cache_key)
    if cached_data:
      if isinstance(cached_data, list) and len(cached_data) > 0:
        selected_cache = random.choice(cached_data)
      else:
        selected_cache = cached_data

      self.book_title = selected_cache["book_title"]
      self.author_name = selected_cache["author_name"]
      self.quotes_list = selected_cache["quotes_list"]
      self.current_quote_index = 0
      self.after(0, self.display_current_quote)
      self.update_status("⚡ Network timeout. Loaded instantly from local cache!")
    else:
      self.quote_label.configure(
          text="❌ Network timeout and no local cache available."
      )
      self.update_status("❌ Failed to connect and no offline backup found.")

    self.set_buttons_state("normal")


if __name__ == "__main__":
  app = QuoteGeneratorApp()
  app.mainloop()
