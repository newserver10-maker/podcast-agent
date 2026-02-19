# -*- coding: utf-8 -*-
import sys
import os
from html.parser import HTMLParser

# Ensure stdout can handle unicode or fallback
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

class ButtonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_button = False
        self.current_tag = None
        self.current_attrs = {}
        self.buttons = []
        self.current_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        # Check for button or button-like elements
        is_button = tag == 'button' or \
                    attrs_dict.get('role') == 'button' or \
                    'mat-card' in attrs_dict.get('class', '') or \
                    'create-new' in attrs_dict.get('class', '') or \
                    'project-button' in attrs_dict.get('class', '') or \
                    'fab' in attrs_dict.get('class', '')

        if is_button:
            self.in_button = True
            self.current_tag = tag
            self.current_attrs = attrs_dict
            self.current_text = ""

    def handle_endtag(self, tag):
        if self.in_button and tag == self.current_tag:
            self.buttons.append({
                'tag': self.current_tag,
                'attrs': self.current_attrs,
                'text': self.current_text.strip()
            })
            self.in_button = False

    def handle_data(self, data):
        if self.in_button:
            self.current_text += data

def main():
    print("Starting analysis...")
    file_path = 'e:/Anti gravity/podcast_agent/debug_add_source_input.html'
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    parser = ButtonParser()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            parser.feed(content)
    except Exception as e:
        print(f"Error parsing file: {e}")
        return

    print(f"Found {len(parser.buttons)} potential buttons:")
    for i, btn in enumerate(parser.buttons):
        try:
            print(f"--- Button {i+1} ---")
            print(f"Tag: {btn['tag']}")
            # Use ascii() or repr() to avoid encoding capability issues in console
            print(f"Text: {ascii(btn['text'])}")  
            print(f"ARIA: {ascii(btn['attrs'].get('aria-label', 'N/A'))}")
            print(f"Class: {ascii(btn['attrs'].get('class', 'N/A'))}")
            print(f"ID: {ascii(btn['attrs'].get('id', 'N/A'))}")
        except Exception as e:
             print(f"Error printing button {i}: {e}")

if __name__ == "__main__":
    main()
