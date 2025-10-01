import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import subprocess
import sys
import threading
import urllib.parse
import os
import re
import json

scraper_process = None
all_results = []
stats = {
    'products_found': 0,
    'pages_processed': 0,
    'total_price': 0,
    'price_count': 0,
    'average_price': 0
}


def run_script():
    global scraper_process, all_results, stats
    query = query_entry.get().strip()
    brand = brand_entry.get().strip()
    start_page = start_page_entry.get().strip() or "1"
    end_page = end_page_entry.get().strip() or "3"

    if not query or not brand:
        messagebox.showerror("Input Error", "Please enter a search query and target brand")
        return

    try:
        start_page_int = int(start_page)
        end_page_int = int(end_page)
        if start_page_int > end_page_int:
            messagebox.showerror("Input Error", "Start page cannot be greater than end page")
            return
    except ValueError:
        messagebox.showerror("Input Error", "Start Page and End Page must be integers")
        return

    run_button.config(state=tk.DISABLED, text="Running…", bg="#388E3C")
    exit_button.config(state=tk.NORMAL)
    result_text.delete(1.0, tk.END)
    for item in results_table.get_children():
        results_table.delete(item)
    all_results.clear()

    stats.update({'products_found':0,'pages_processed':0,'total_price':0,'price_count':0,'average_price':0})
    update_stats()
    root.update()

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={encoded_query}"
    url_label.config(text=f"Search URL: {search_url}")

    thread = threading.Thread(target=execute_script, args=(search_url, brand, start_page_int, end_page_int))
    thread.daemon = True
    thread.start()

def execute_script(search_url, target_brand, start_page, end_page):
    global scraper_process, all_results, stats
    try:
        scraper_process = subprocess.Popen(
            [sys.executable, "-u", "wildberries_scraper.py", search_url, target_brand, str(start_page), str(end_page)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        for line in scraper_process.stdout:
            root.after(0, append_text, line)
            extract_stats(line)
        scraper_process.wait()
        stderr = scraper_process.stderr.read()
        if stderr:
            root.after(0, append_text, f"\n[ERROR]: {stderr}\n")
    except Exception as e:
        root.after(0, append_text, f"\n[Execution failed]: {str(e)}\n")
    finally:
        scraper_process = None
        root.after(0, reset_ui)

def append_text(text):
    line = text.strip()
    try:
        if line.startswith('{') and line.endswith('}'):
            data = json.loads(line)
            type_ = data.get('type')
            msg = data.get('message', str(data))
            if type_ == 'info':
                result_text.insert(tk.END, msg + '\n', 'info')
            elif type_ == 'warning':
                result_text.insert(tk.END, msg + '\n', 'warning')
            elif type_ in ['error','critical_error']:
                result_text.insert(tk.END, msg + '\n', 'error')
            else:
                result_text.insert(tk.END, msg + '\n')
        else:
            result_text.insert(tk.END, text + '\n')
        result_text.see(tk.END)
    except json.JSONDecodeError:
        result_text.insert(tk.END, text + '\n')
        result_text.see(tk.END)

def reset_ui():
    run_button.config(state=tk.NORMAL, text="Check Rankings", bg="#4CAF50")

def exit_app():
    global scraper_process
    if scraper_process and scraper_process.poll() is None:
        try: scraper_process.terminate()
        except Exception: pass
    root.destroy()

def save_results():
    if not all_results:
        messagebox.showinfo("Info", "No results to save yet.")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv")])
    if not file_path: return
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for line in all_results:
                f.write(line + "\n")
        messagebox.showinfo("Success", f"Results saved to {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not save results: {e}")

def clear_results():
    result_text.delete(1.0, tk.END)
    for item in results_table.get_children():
        results_table.delete(item)
    stats.update({'products_found':0,'pages_processed':0,'total_price':0,'price_count':0,'average_price':0})
    update_stats()

def extract_stats(line):
    global all_results, stats
    all_results.append(line.strip())
    line = line.strip()
    try:
        if line.startswith('{') and line.endswith('}'):
            data = json.loads(line)
            type_ = data.get('type')
            if type_ == 'product_found':
                product = data.get('product', {})
                price_numeric = product.get('price_numeric')
                results_table.insert('', 'end', values=(
                    product.get('global_position',''),
                    product.get('page',''),
                    product.get('brand',''),
                    product.get('name','')[:50],
                    f"{price_numeric} RUB" if price_numeric else product.get('price_text','')
                ))
                if price_numeric and price_numeric>0:
                    stats['products_found'] +=1
                    stats['total_price'] += price_numeric
                    stats['price_count'] +=1
                    stats['average_price'] = round(stats['total_price']/stats['price_count'])
                    update_stats()
            elif type_ in ['page_complete','summary']:
                page_num = data.get('page', data.get('pages_processed',0))
                if page_num > stats['pages_processed']:
                    stats['pages_processed'] = page_num
                    update_stats()
    except:
        pass

def update_stats():
    products_found_label.config(text=f"Products Found: {stats['products_found']}")
    pages_processed_label.config(text=f"Pages Processed: {stats['pages_processed']}")
    avg_price_label.config(text=f"Average Price: {stats['average_price']} RUB")


root = tk.Tk()
root.title("Wildberries Product Rank Checker")
root.geometry("1200x800")
root.configure(bg="#f5f5f5")
root.resizable(True,True)

style = ttk.Style(root)
style.theme_use("clam")
style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#4a90e2")
style.configure("Treeview", rowheight=25, font=("Segoe UI", 10))
style.map('Treeview', background=[('selected','#cce5ff')], foreground=[('selected','#000000')])
style.configure("TButton", font=("Segoe UI",10,"bold"), padding=6)
style.map("TButton",
          foreground=[('active','white')],
          background=[('active','#1976D2')])

header_frame = tk.Frame(root, bg="#4a90e2", pady=10)
header_frame.pack(fill=tk.X)
header_label = tk.Label(header_frame, text="Wildberries Product Rank Checker", font=("Segoe UI", 18, "bold"), bg="#4a90e2", fg="white")
header_label.pack()


content_frame = tk.Frame(root, bg="#f5f5f5")
content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

input_panel = tk.Frame(content_frame, bg="#ffffff", bd=1, relief=tk.RIDGE, padx=10, pady=10)
input_panel.pack(fill=tk.X, pady=5)

tk.Label(input_panel, text="Product Search Query:", bg="#ffffff", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
query_entry = tk.Entry(input_panel, width=70, font=("Segoe UI",10))
query_entry.pack(pady=5, fill=tk.X)
query_entry.bind("<Return>", lambda event: run_script())
query_entry.focus()

tk.Label(input_panel, text="Target Brand:", bg="#ffffff", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(10,0))
brand_entry = tk.Entry(input_panel, width=30, font=("Segoe UI",10))
brand_entry.pack(pady=5, anchor=tk.W)
brand_entry.insert(0,"MediS")

page_frame = tk.Frame(input_panel, bg="#ffffff")
page_frame.pack(pady=5, fill=tk.X)
tk.Label(page_frame, text="Start Page:", bg="#ffffff").pack(side=tk.LEFT)
start_page_entry = tk.Entry(page_frame, width=5)
start_page_entry.pack(side=tk.LEFT, padx=5)
start_page_entry.insert(0,"1")
tk.Label(page_frame, text="End Page:", bg="#ffffff").pack(side=tk.LEFT, padx=(20,5))
end_page_entry = tk.Entry(page_frame, width=5)
end_page_entry.pack(side=tk.LEFT)
end_page_entry.insert(0,"3")

url_label = tk.Label(input_panel, text="Search URL will appear here", fg="#1976D2", bg="#ffffff", wraplength=850, font=("Segoe UI", 9))
url_label.pack(pady=5, anchor=tk.W)

run_button = tk.Button(input_panel, text="Check Rankings", command=run_script, bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"))
run_button.pack(pady=10)

stats_panel = tk.Frame(content_frame, bg="#f5f5f5")
stats_panel.pack(fill=tk.X, pady=5)
products_found_label = tk.Label(stats_panel, text="Products Found: 0", bg="#E3F2FD", fg="#0D47A1", font=("Segoe UI",10,"bold"), padx=10, pady=5)
products_found_label.pack(side=tk.LEFT, padx=5)
pages_processed_label = tk.Label(stats_panel, text="Pages Processed: 0", bg="#E8F5E9", fg="#1B5E20", font=("Segoe UI",10,"bold"), padx=10, pady=5)
pages_processed_label.pack(side=tk.LEFT, padx=15)
avg_price_label = tk.Label(stats_panel, text="Average Price: 0 RUB", bg="#FFF3E0", fg="#E65100", font=("Segoe UI",10,"bold"), padx=10, pady=5)
avg_price_label.pack(side=tk.LEFT, padx=15)

results_notebook = ttk.Notebook(content_frame)
results_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

table_frame = tk.Frame(results_notebook)
results_notebook.add(table_frame, text="Results Table")
results_table = ttk.Treeview(table_frame, columns=('Position','Page','Brand','Name','Price'), show='headings')
for col in results_table["columns"]:
    results_table.heading(col, text=col)
results_table.column('Position', width=80, anchor='center')
results_table.column('Page', width=60, anchor='center')
results_table.column('Brand', width=120, anchor='w')
results_table.column('Name', width=350, anchor='w')
results_table.column('Price', width=100, anchor='e')

table_scroll_y = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=results_table.yview)
table_scroll_x = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=results_table.xview)
results_table.configure(yscrollcommand=table_scroll_y.set, xscrollcommand=table_scroll_x.set)
results_table.grid(row=0, column=0, sticky='nsew')
table_scroll_y.grid(row=0, column=1, sticky='ns')
table_scroll_x.grid(row=1, column=0, sticky='ew')
table_frame.grid_rowconfigure(0, weight=1)
table_frame.grid_columnconfigure(0, weight=1)

raw_frame = tk.Frame(results_notebook)
results_notebook.add(raw_frame, text="Raw Output")
result_text = scrolledtext.ScrolledText(raw_frame, width=100, height=25, font=("Consolas", 9))
result_text.tag_config('info', foreground='blue')
result_text.tag_config('warning', foreground='orange')
result_text.tag_config('error', foreground='red')
result_text.pack(fill=tk.BOTH, expand=True)

buttons_frame = tk.Frame(content_frame, bg="#f5f5f5")
buttons_frame.pack(pady=10)
save_button = tk.Button(buttons_frame, text="💾 Save Results", command=save_results, bg="#2196F3", fg="white", font=("Segoe UI",10,"bold"), padx=10, pady=5)
save_button.pack(side=tk.LEFT, padx=5)
clear_button = tk.Button(buttons_frame, text="🧹 Clear Results", command=clear_results, bg="#FF9800", fg="white", font=("Segoe UI",10,"bold"), padx=10, pady=5)
clear_button.pack(side=tk.LEFT, padx=5)
exit_button = tk.Button(buttons_frame, text="❌ Exit", command=exit_app, bg="#f44336", fg="white", font=("Segoe UI",10,"bold"), padx=10, pady=5)
exit_button.pack(side=tk.LEFT, padx=5)

root.mainloop()
