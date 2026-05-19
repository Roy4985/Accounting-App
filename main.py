import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from datetime import datetime
import csv
from tkcalendar import DateEntry
import os
import shutil

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


#This class is for everything database related
class DatabaseManager:
    #This will create the db file (and sqlite3 setups)
    def __init__(self, db_name="store.db"):
        self.conn = sqlite3.connect(db_name)

        self.c = self.conn.cursor()

        self.create_tables()

        self.run_migrations()

    #Migration for 1.2 update (Add description columns without destrying the already in use db)
    def run_migrations(self):
        try:
            self.c.execute("ALTER TABLE transactions ADD COLUMN description TEXT")
            self.conn.commit()
            print("Database upgraded: Added description column.")
        except sqlite3.OperationalError:
            pass

    #This will create the required tables (stores and transactions if not created) and check if stores is empty to add the default stores
    def create_tables(self):
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                       name TEXT
                       )
        """)

        self.c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                       store_id INTEGER,
                       parent_id INTEGER,
                       date TEXT,
                       type TEXT,
                       category TEXT,
                       amount REAL,
                       currency TEXT,
                       payment_method TEXT
                       )
        """)

        self.c.execute("""CREATE TABLE IF NOT EXISTS settings (
                       key TEXT PRIMARY KEY,
                       value REAL
                       )
        """)

        self.c.execute("""CREATE TABLE IF NOT EXISTS daily_sales (
                       date TEXT,
                       store_id INTEGER,
                       amount REAL,
                       PRIMARY KEY (store_id, date))""")

        self.c.execute("CREATE INDEX IF NOT EXISTS idx_store_date ON transactions(store_id, date)")
        
        self.c.execute("CREATE INDEX IF NOT EXISTS idx_parent ON transactions(parent_id)")

        self.seed_data()
        self.seed_settings()

    def seed_settings(self):
        default = {
            "main_rate" : 15.0,
            "tva_rate" : 7.0,
            "comm_rate": 3.0,
            "freight_rate": 33.0,
            "exchange_rate": 89500.0,
        }

        for key, val in default.items():
            self.c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (key,val))
        self.conn.commit()

    def get_rate(self, key):
        self.c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        res = self.c.fetchone()
        return res[0] if res else 0.0

    def update_rate(self, key, value):
        self.c.execute("UPDATE settings SET value = ? WHERE key = ?", (value,key))
        self.conn.commit()

    #This will check if the stores table is empty, if it is, it will add the default stores (he bas ta nzid l branches)
    def seed_data(self):
        default_branches = ["LeMall Dbayye", "City Center", "City Mall", "Koura Branch",
                                "Main Vault", "TVA Account", "Bank Commission", "Cost of goods", "Freight"]
        
        for branch in default_branches:
            self.c.execute("SELECT count(*) FROM stores WHERE name = ?", (branch,))
            if self.c.fetchone()[0] == 0:
                print(f"Adding missing branch: {branch}")
                self.c.execute("INSERT INTO stores (name) VALUES (?)", (branch,))
        self.conn.commit()


    def get_store_names(self):
        self.c.execute("SELECT name FROM stores")

        names = []

        for row in self.c.fetchall():
            names.append(row[0])
        return names
    
    def get_store_id(self, store_name):
        self.c.execute("SELECT id FROM stores WHERE name = ?", (store_name,))
        #Safety check
        result = self.c.fetchone()
        if not result:
            print(f"Error Store '{store_name}' not found")
            return
        return result[0]
    
    def save_daily_sale(self, store_name, t_date, t_amount):
    
        store_id = self.get_store_id(store_name)
        #In case of an error where there is no ID provided
        if not store_id:
            return

        #I used INSERT OR REPLACE to overwrite a sale, if its in the same day, same store
        self.c.execute("INSERT OR REPLACE INTO daily_sales (date, store_id, amount) VALUES (?,?,?)", (t_date, store_id, t_amount))

        self.conn.commit()

    def get_daily_sale(self, store_name, t_date):
        store_id = self.get_store_id(store_name)

        self.c.execute("SELECT amount FROM daily_sales WHERE store_id = ? AND date = ?", (store_id, t_date))
        amount = self.c.fetchone()
        if amount == None:
            return 0
        else :
            return amount[0]
        


        
    def add_transactions(self, store_name, t_date, t_type, category, amount, currency, p_method, parent_id=None, description=None):
        self.c.execute("SELECT id FROM stores WHERE name = ?", (store_name,))
        result = self.c.fetchone()

        if result:
            store_id = result[0]

            self.c.execute("INSERT INTO transactions (store_id, parent_id, date, type, category, amount, currency, payment_method, description) VALUES (?,?,?,?,?,?,?,?,?)", (store_id, parent_id,t_date, t_type, category, amount, currency, p_method, description))
            self.conn.commit()
            return self.c.lastrowid
        else:
            print("Error, Store not found")

    def get_transactions(self, store_name):
        self.c.execute("""
            SELECT t.id, t.date, t.type, t.category, t.amount, t.currency, t.payment_method, IFNULL(t.description, '') FROM transactions t
            JOIN stores s ON t.store_id = s.id
            WHERE s.name = ?
            ORDER BY t.date DESC
        """, (store_name,))

        return self.c.fetchall()
    
    def update_transaction_full(self, record_id, new_date, new_cat, new_amt, new_desc):
        self.c.execute("""
                       UPDATE transactions
                       SET date = ?, category = ?, amount = ?, description = ?
                       WHERE id = ?
                       """, (new_date, new_cat, new_amt, new_desc, record_id))
        
        self.c.execute("UPDATE transactions SET date = ? WHERE parent_id = ?",(new_date, record_id))

        self.conn.commit()

    def update_smart_pair(self, parent_id, dest_store_name, category_keyword, new_amount):
        self.c.execute("""
            UPDATE transactions 
            SET amount = ? 
            WHERE parent_id = ? 
            AND store_id = (SELECT id FROM stores WHERE name = ?)
        """, (new_amount, parent_id, dest_store_name))

        like_query = f"{category_keyword}%"
        self.c.execute("""
                        UPDATE transactions
                       SET amount = ?
                       WHERE parent_id = ?
                       AND category LIKE ?""", (new_amount, parent_id, like_query))

        self.conn.commit()

    def delete_transaction(self, trans_id):
        self.c.execute("DELETE FROM transactions WHERE id = ?", (trans_id,))
        self.conn.commit()

    def delete_smart_chain(self, record_id):
        self.c.execute("DELETE FROM transactions WHERE parent_id = ?", (record_id,))

        self.c.execute("DELETE FROM transactions WHERE id = ?",(record_id,))

        self.conn.commit()


    def get_balance_summary(self):
        query = """
            SELECT s.name, t.currency, t.payment_method, 
                   SUM(CASE WHEN t.type = 'Income' THEN t.amount ELSE -t.amount END) as balance
            FROM transactions t
            JOIN stores s ON t.store_id = s.id
            GROUP BY s.name, t.currency, t.payment_method
        """
        self.c.execute(query)
        return self.c.fetchall()
        
#This class will be used for the user interface (GUI)
class StoreApp:
    #This will create the root of the window, link the db class and setup the page
    def __init__(self, root):
        self.root = root
        self.root.title("Management System")
        try:
            self.root.iconbitmap("dollar.ico")
        except:
            pass

        self.root.geometry("1200x800")
        def maximize_window():
            try:
                self.root.state("zoomed") 
            except Exception:
                pass

        self.root.after(100, maximize_window)

        self.db = DatabaseManager()
        self.auto_backup()

        #Color dictionnary
        self.colors = {
            "bg": "#242424",           
            "header": "#1a1a1a",       
            "card": "#333333",         
            "text": "#ffffff",        
            "accent": "#1f538d",      
            "success": "#2cc985",      
            "danger": "#c0392b",      
            "white": "#ffffff"
        }

        self.setup_styles()

        self.system_accounts = ["Main Vault", "TVA Account", "Bank Commission", "Cost of goods", "Freight"]

        self.category_list = [
            "Salaries",
            "Rent",
            "Yearly Fees",
            "Electricity Chiller",
            "Phone",
            "Various",
            "Cost of goods",
            "Cleaner",
            "Main",
        ]

        self.main_category_list = [
            "Upgrades",
            "Salaries",
            "Bank Fees",
            "Audit",
            "Bags & EAS",
            "Social Media",
            "Electricity & Phone",
            "Profit Distribution",
            "Yearly Fees",
            "Rent",
            "Transportation",
            "Various",
        ]

        self.current_data = []

        self.setup_header()
        self.setup_inputs()
        self.setup_table()
        self.view_records()
        self.toggle_category_state()

    def auto_backup(self):
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)

            today = datetime.now().strftime('%Y-%m-%d')
            backup_file = os.path.join(backup_dir, f"backup_{today}.db")

            if not os.path.exists(backup_file) and os.path.exists("store.db"):
                try:
                    shutil.copy("store.db",backup_file)
                    print(f"Auto Backup created for {today}")
                except Exception as e:
                    print(f"Auto-backup failed: {e}")

    def setup_header(self):
        #the frame for the header
        header_frame = ctk.CTkFrame(self.root, fg_color=self.colors["header"], height=70, corner_radius=0)
        header_frame.pack(fill="x")

        #Now the Title on top of the page
        title_label = ctk.CTkLabel(header_frame, text="Select Branch", text_color = "white", font=("Roboto Medium", 24))
        title_label.pack(side=tk.LEFT, padx=30, pady=15)

        settings_btn = ctk.CTkButton(header_frame, text="⚙ Settings", width=120, height=35, fg_color="transparent", 
                                     border_width=2, border_color="#3e3e3e", hover_color="#3e3e3e", 
                                     font=("Segoe UI", 11, "bold"),cursor="hand2",
                                 command=self.open_settings_window)
        settings_btn.pack(side=tk.RIGHT, padx=20)

        balance_btn = ctk.CTkButton(header_frame, text="📊 Balances", width=120, height=35, fg_color="#8e44ad", 
                                 font=("Segoe UI", 11, "bold"), hover_color="#9b59b6",cursor="hand2",
                                 command=self.open_balances_window)
        balance_btn.pack(side=tk.RIGHT, padx=5)

        recon_btn = ctk.CTkButton(header_frame, text="📅 Daily Recon", width=120, height=35, fg_color="#e67e22", hover_color="#d35400", 
                                 font=("Segoe UI", 11, "bold"), cursor="hand2",
                                 command=self.open_daily_reconciliation_window)
        recon_btn.pack(side=tk.RIGHT, padx=5)

        all_stores = self.db.get_store_names()

        #Now under it we want to branch dropdown menu
        self.store_var = ctk.StringVar(value=all_stores[0])
        self.store_combo = ctk.CTkComboBox(header_frame, width=200, height=35, variable=self.store_var, values=all_stores, state="readonly", command=self.on_branch_change)

        self.store_combo.pack(side=tk.RIGHT, padx=20)

    def on_branch_change(self, choice):
        self.toggle_category_state()
        self.update_filter_dropdown()

        try:
            self.no_main_var.set(0)
        except AttributeError:
            pass


    def setup_inputs(self):
        master_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        master_frame.pack(fill="x", padx=20, pady=15)

        #Input side 
        input_frame = ctk.CTkFrame(master_frame, fg_color=self.colors["card"], corner_radius=15)
        input_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0,10))

        ctk.CTkLabel(input_frame, text="New Transaction", font=("Roboto Medium", 16), text_color="#bdc3c7").grid(row=0, column=0,columnspan=6, pady=(15, 15),sticky="w",padx=15)

        # --- Row 1: date | Type | Category ---
        ctk.CTkLabel(input_frame, text="Date").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.date_entry = DateEntry(input_frame, width=12, background="#1f538d", foreground='white', borderwidth=0, font=("Segoe UI", 12), date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=1, column=1, padx=10, pady=5, ipady=5)

        ctk.CTkLabel(input_frame, text="Type").grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.type_var = ctk.StringVar(value="Income")
        self.type_combo = ctk.CTkComboBox(input_frame, variable=self.type_var, values=["Income","Expense"], width=120, state="readonly", command=self.toggle_category_state)
        self.type_combo.grid(row=1, column=3, padx=10, pady=5)

        ctk.CTkLabel(input_frame, text="Category").grid(row=1, column=4, padx=10, pady=5, sticky="w")
        self.cat_var = ctk.StringVar(value=self.category_list[0])
        self.cat_combo = ctk.CTkComboBox(input_frame, variable=self.cat_var, values=self.category_list, state="readonly", width=160)
        self.cat_combo.grid(row=1, column=5, padx=10, pady=5)

        # --- Row 2: Amount | Currency | Method ---
        ctk.CTkLabel(input_frame, text="Amount").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.amount_entry = ctk.CTkEntry(input_frame, width=120, placeholder_text="0.00")
        self.amount_entry.grid(row=2, column=1, padx=10, pady=5)
        self.amount_entry.bind('<Return>', lambda event: self.add_records())

        ctk.CTkLabel(input_frame, text="Currency").grid(row=2, column=2, padx=10, pady=5, sticky="w")
        self.currency_var = ctk.StringVar(value="USD ($)")
        self.cur_combo = ctk.CTkComboBox(input_frame, variable=self.currency_var, values=["USD ($)", "Lira (LBP)"], state="readonly", width=120)
        self.cur_combo.grid(row=2, column=3, padx=10, pady=5)

        ctk.CTkLabel(input_frame, text="Payment Method").grid(row=2, column=4, padx=10, pady=5, sticky="w")
        self.paym_var = ctk.StringVar(value="Cash")
        self.paym_combo = ctk.CTkComboBox(input_frame, variable=self.paym_var, values=["Cash", "Card"], state="readonly", width=120)
        self.paym_combo.grid(row=2, column=5, padx=10, pady=5) 

        # --- Row 3: Description | Checkbox ---
        ctk.CTkLabel(input_frame, text="Description (Opt):").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.desc_entry = ctk.CTkEntry(input_frame, width=300, placeholder_text="Details...")
        self.desc_entry.grid(row=3, column=1, columnspan=3, padx=10, pady=5, sticky="w")

        self.no_main_var = ctk.IntVar(value=0)
        no_main_chk = ctk.CTkCheckBox(input_frame, text="Skip Main Tax", variable=self.no_main_var, border_width=2, checkbox_width=20, checkbox_height=20)
        no_main_chk.grid(row=3, column=4, columnspan=2, sticky="w", padx=10, pady=5)

        # --- Row 4: Buttons ---
        input_btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_btn_frame.grid(row=4, column=0, columnspan=6, pady=20, sticky="ew")

        # To give both buttons equal sapce
        input_btn_frame.columnconfigure(0, weight=1)
        input_btn_frame.columnconfigure(1, weight=1)

        add_btn = ctk.CTkButton(input_btn_frame, text="+ ADD RECORD", height=40, fg_color=self.colors["success"], hover_color="#27ae60", font=("Segoe UI", 12, "bold"), cursor="hand2", command=self.add_records)
        add_btn.grid(row=0, column=0, sticky="ew", padx=10)

        exchange_btn = ctk.CTkButton(input_btn_frame, text="Exchange", height=40, fg_color="#e67e22", hover_color="#d35400", font=("Segoe UI", 12 , "bold"), cursor="hand2",  command= self.open_exchange_window)
        exchange_btn.grid(row=0, column=1, sticky="ew", padx=10)

        # --- FILTER SIDE ---
        filter_frame = ctk.CTkFrame(master_frame, fg_color=self.colors["card"], corner_radius=15)
        filter_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=(10,0))

        ctk.CTkLabel(filter_frame, text="Filters", font=("Roboto Medium", 16), text_color="#bdc3c7").grid(row=0, column=0, columnspan=4, pady=(15,15), sticky="w", padx=15)

        # --- Row 1: Type & Category ---
        ctk.CTkLabel(filter_frame, text="Filter Type:").grid(row=1, column=0, padx=10, pady=5)
        self.filter_type_var = ctk.StringVar(value="All")
        self.filter_type = ctk.CTkComboBox(filter_frame, variable=self.filter_type_var, values=["All", "Income", "Expense"], width=100, state="readonly", command=self.update_filter_dropdown)
        self.filter_type.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(filter_frame, text="Filter Category:").grid(row=1, column=2, padx=10, pady=5)
        full_cat_list = ["All", "Sales", "Investment", "Exchange In/Out", "Bank Transfer In/Out"] + self.category_list
        self.filter_cat_var = ctk.StringVar(value="All")
        self.filter_cat = ctk.CTkComboBox(filter_frame, variable=self.filter_cat_var, values= full_cat_list, width=140, state="readonly", command=lambda e: self.view_records())
        self.filter_cat.grid(row=1, column=3, padx=5, pady=5)

        # --- Row 2: Currency | Method ---
        ctk.CTkLabel(filter_frame, text="Currency:").grid(row=2, column=0, padx=10, pady=5)
        self.filter_curr_var = ctk.StringVar(value="All")
        self.filter_curr = ctk.CTkComboBox(filter_frame, variable=self.filter_curr_var, values= ["All", "USD ($)", "Lira (LBP)"], width=100, state="readonly", command=lambda e: self.view_records())
        self.filter_curr.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkLabel(filter_frame, text="Method:").grid(row=2, column=2, padx=10, pady=5)
        self.filter_paym_var = ctk.StringVar(value="All")
        self.filter_paym = ctk.CTkComboBox(filter_frame, variable=self.filter_paym_var, values= ["All", "Cash", "Card"], width=140, state="readonly", command=lambda e: self.view_records())
        self.filter_paym.grid(row=2, column=3, padx=5, pady=5)
        
        # --- Row 3: Dates ---
        ctk.CTkLabel(filter_frame, text="From:").grid(row=3, column=0, padx=10, pady=5)
        self.date_from = DateEntry(filter_frame, width=12, background="#2c3e50", foreground='white', borderwidth=0, font=("Segoe UI", 12), date_pattern='yyyy-mm-dd')
        self.date_from.delete(0, "end")
        self.date_from.grid(row=3, column=1, padx=5, pady=5, ipady=3)

        ctk.CTkLabel(filter_frame, text="To:").grid(row=3, column=2, padx=10, pady=5)
        self.date_to = DateEntry(filter_frame, width=12, background="#2c3e50", foreground='white', borderwidth=0, font=("Segoe UI", 12), date_pattern='yyyy-mm-dd')
        self.date_to.delete(0, "end")
        self.date_to.grid(row=3, column=3, padx=5, pady=5, ipady=3)

        # --- Row 5: Buttons ---
        filter_btn_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        filter_btn_frame.grid(row=4, column=0, columnspan=4, pady=20)

        ctk.CTkButton(filter_btn_frame, text="Apply Filter", width=80, cursor="hand2", command=self.view_records).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(filter_btn_frame, text="Reset", width=80, fg_color="transparent", border_width=1, cursor="hand2", command = self.reset_filters).pack(side=tk.LEFT, padx=5)


    def setup_table(self):
        main_content = ctk.CTkFrame(self.root, fg_color="transparent")
        main_content.pack(fill="both", expand=True, padx=20, pady=(0,20))


        tree_frame = ctk.CTkFrame(main_content)
        tree_frame.pack(fill="both", expand=True)

        cols = ("ID", "Date", "Type", "Category", "Amount", "Currency", "Payment Method", "Description")

        visible_cols = ("Date", "Type", "Category", "Amount", "Currency", "Payment Method", "Description")

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", displaycolumns=visible_cols, selectmode="browse")

        self.tree.column("Date", width=100, anchor="center")
        self.tree.column("Type", width=80, anchor="center")
        self.tree.column("Category", width=150, anchor="w")
        self.tree.column("Description", width=250, anchor="w")
        self.tree.column("Amount", width=100, anchor="e")  
        self.tree.column("Currency", width=80, anchor="center")
        self.tree.column("Payment Method", width=100, anchor="center")
        

        for col in visible_cols:
            self.tree.heading(col, text=col)

        scrollbar = ctk.CTkScrollbar(tree_frame, orientation="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind('<Delete>', lambda event: self.delete_record())
        self.tree.bind("<Button-3>", self.show_context_menu)


        bottom_frame = ctk.CTkFrame(main_content, fg_color="transparent")
        bottom_frame.pack(fill="x", pady=10)

        export_btn = ctk.CTkButton(bottom_frame, text="Export to Excel", fg_color=self.colors["accent"], hover_color="#154360", font=("Segoe UI", 12, "bold"), height=35, cursor="hand2", command=self.export_to_excel)
        export_btn.pack(side="left")

        #He placeholder ma bt bayyin b bayyin mahala l hateto b show records and __init__ he bas just to be safe
        self.status_label = ctk.CTkLabel(bottom_frame, text="Loading...", font=("Consolas", 12, "bold"), text_color="#bdc3c7")
        self.status_label.pack(side="right")

        self.grand_total_label = ctk.CTkLabel(bottom_frame, text="Total: $0.00", font=("Consolas", 16, "bold"), text_color="#2cc985")
        self.grand_total_label.pack(side="right", padx=20)

        #Right click menu part 
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#2b2b2b", fg="white", activebackground=self.colors["accent"], activeforeground="white")

        self.context_menu.add_command(label="Edit Record", command=self.open_edit_window)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Record", command=self.delete_record)

    def show_context_menu(self, event):
        try:
            item_id = self.tree.identify_row(event.y)

            if item_id:
                self.tree.selection_set(item_id)
                self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def open_edit_window(self):
        selected_item = self.tree.selection()

        if not selected_item:
            return
        
        row_data = self.tree.item(selected_item)['values']
        clicked_id = row_data[0]

        self.db.c.execute("SELECT parent_id FROM transactions WHERE id = ?", (clicked_id,))
        result = self.db.c.fetchone()

        if result and result[0]:
            messagebox.showwarning(
                "Locked Record",
                "This is an auto-generated system record.\n\nTo change it, please go to the original branch and edit the source transaction"
            )
            return

        final_id = clicked_id

        self.db.c.execute("SELECT * FROM transactions WHERE id = ?", (final_id,))
        record = self.db.c.fetchone()

        old_date = record[3]
        old_cat = record[5]
        old_amt = record[6]
        old_type = record[4]
        old_paym = record[8]
        old_desc = record[9] if record[9] else ""

        edit_win = ctk.CTkToplevel(self.root)
        edit_win.title("Edit Record")
        edit_win.geometry("350x500")
        edit_win.grab_set()
        edit_win.focus()

        ctk.CTkLabel(edit_win, text="Edit Transaction", font=("Roboto Medium", 18), text_color=self.colors["accent"]).pack(pady=(20, 10))

        # --- Card Container ---
        card = ctk.CTkFrame(edit_win, fg_color=self.colors["card"], corner_radius=10)
        card.pack(padx=20, pady=10, fill="both", expand=True)

        ctk.CTkLabel(card, text="Date:", font=("Segoe UI", 12)).pack(pady=(15, 0))
        date_entry = DateEntry(card, width=15, background="#1f538d", foreground="white", borderwidth=0, date_pattern='yyyy-mm-dd')
        date_entry.set_date(old_date)
        date_entry.pack(pady=(5, 10))

        valid_categories = []
        store = self.store_combo.get()
        if old_type == "Income":
                    valid_categories = ["Sales", "Investment"]
        else:
            if store == "Main Vault":
                valid_categories = self.main_category_list
            else:
                valid_categories = self.category_list

        ctk.CTkLabel(card, text="Category:", font=("Segoe UI", 12)).pack(pady=0)

        cat_var = ctk.StringVar(value=old_cat)
        cat_entry = ctk.CTkComboBox(card, values=valid_categories, variable=cat_var, state="readonly", width=200)
        if old_cat == "Main":
            cat_entry.configure(state="disabled")
        else :
            cat_entry.configure(state="readonly")
        cat_entry.pack(pady=(5, 10))

        ctk.CTkLabel(card, text="Description:", font=("Segoe UI", 12)).pack(pady=0)
        desc_entry = ctk.CTkEntry(card, width=200)
        desc_entry.insert(0, old_desc)
        desc_entry.pack(pady=(5, 10))

        ctk.CTkLabel(card, text="Amount:", font=("Segoe UI", 12)).pack(pady=0)
        amt_entry = ctk.CTkEntry(card, width=200)
        amt_entry.insert(0, str(old_amt))
        amt_entry.pack(pady=(5, 15))

        def save_changes():
            try:
                new_date = date_entry.get()
                new_cat = cat_entry.get()
                new_amt = float(amt_entry.get())
                new_desc = desc_entry.get()

                self.db.update_transaction_full(final_id, new_date, new_cat, new_amt, new_desc)

                if old_type == "Income" and new_amt != old_amt:

                    main_rate = self.db.get_rate("main_rate")
                    tva_rate = self.db.get_rate("tva_rate")
                    comm_rate = self.db.get_rate("comm_rate")

                    val_main = round(new_amt * (main_rate / 100), 2)
                    val_tva = round(new_amt * (tva_rate / 100), 2)

                    self.db.update_smart_pair(final_id, "Main Vault", "Main", val_main)
                    self.db.update_smart_pair(final_id, "TVA Account", "TVA", val_tva)

                    if old_paym == "Card":
                        val_comm = round(new_amt * (comm_rate / 100), 2)
                        self.db.update_smart_pair(final_id, "Bank Commission", "Card Commission",val_comm)
                    
                elif old_type == "Expense" and old_cat == "Main" and new_amt != old_amt:
                    self.db.update_smart_pair(final_id, "Main Vault", "from", new_amt)

                messagebox.showinfo("Success", "Record Updated!")
                edit_win.destroy()
                self.view_records()
            except ValueError:
                messagebox.showerror("Error", "Amount must be a number")

        ctk.CTkButton(edit_win, text="SAVE CHANGES", command=save_changes, fg_color=self.colors["success"], hover_color="#27ae60", font=("Segoe UI", 12, "bold"), height=40).pack(pady=20, padx=20, fill="x")

    def open_settings_window(self):
        # --- Window ---
        top = ctk.CTkToplevel(self.root)
        top.title("Configure Rates")
        top.geometry("320x400")
        top.grab_set()
        top.focus()

        # --- Header ---

        ctk.CTkLabel(top, text="Update Tax Rates", font=("Roboto Medium", 18), 
                 text_color=self.colors["accent"]).pack(pady=(20, 10))
        
        form_frame = ctk.CTkFrame(top, fg_color=self.colors["card"], corner_radius=10)
        form_frame.pack(padx=20, pady=10, fill="both", expand=True)

        def make_row(row, label_text, key):
            ctk.CTkLabel(form_frame, text=label_text, font=("Segoe UI", 12)).grid(row=row, column=0, padx=15, pady=12, sticky="w")
            
            
            entry = ctk.CTkEntry(form_frame, width=100, justify="center")
            entry.grid(row=row, column=1, padx=15, pady=12)
            
            current_val = self.db.get_rate(key) 
            entry.insert(0, str(current_val))
            return entry

        e_main = make_row(0, "Main Vault (%):", "main_rate")
        e_tva  = make_row(1, "TVA Tax (%):", "tva_rate")
        e_comm = make_row(2, "Card Comm (%):", "comm_rate")
        e_frgt = make_row(3, "Freight (%):", "freight_rate")
        e_exr = make_row(4, "Exchange Rate:", "exchange_rate")

        def save():
            try:
                self.db.update_rate("main_rate", float(e_main.get()))
                self.db.update_rate("tva_rate", float(e_tva.get()))
                self.db.update_rate("comm_rate", float(e_comm.get()))
                self.db.update_rate("freight_rate", float(e_frgt.get()))
                self.db.update_rate("exchange_rate", float(e_exr.get()))
                
                messagebox.showinfo("Success", "Rates updated!", parent=top) 
                top.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers", parent=top)

        # --- Save Button ---
        save_btn = ctk.CTkButton(top, text="SAVE CHANGES", command=save, 
                             fg_color=self.colors["success"], hover_color="#27ae60", font=("Segoe UI", 12, "bold"), height=40)
        save_btn.pack(pady=20, padx=20, fill="x")

    def open_exchange_window(self):
        # -- Popup Window ---
        top = ctk.CTkToplevel(self.root)
        top.title("Exchange currency")
        top.geometry("400x550")
        top.grab_set()
        top.focus()

        # --- Tabview ---
        tabview = ctk.CTkTabview(top, width=350, height=480, corner_radius=10, fg_color=self.colors["bg"],
                                 segmented_button_selected_color=self.colors["accent"],
                                 segmented_button_selected_hover_color="#154360")
        tabview.pack(fill="both", expand=True, padx=20, pady=20)

        tabview.add("Currency Exchange")
        tabview.add("Bank Transfer")

        tab_ce = tabview.tab("Currency Exchange")
        tab_bt = tabview.tab("Bank Transfer")

        # === TAB 1 : Currency Exchange === #
        ctk.CTkLabel(tab_ce, text="Amount to Change:", font=("Segoe UI", 12)).pack(anchor="w", pady=(10, 5), padx=20)
        amt_entry_ce = ctk.CTkEntry(tab_ce, width=300, placeholder_text="0.00")
        amt_entry_ce.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(tab_ce, text="Direction:", font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 5), padx=20)
        dir_combo_var_ce = ctk.StringVar(value="USD -> LBP")
        dir_combo_ce = ctk.CTkComboBox(tab_ce, variable=dir_combo_var_ce, values=["USD -> LBP", "LBP -> USD"], state="readonly", width=300)
        dir_combo_ce.pack(fill="x", padx=20, pady=(0,15))

        ctk.CTkLabel(tab_ce, text="Exchange Rate:", font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 5), padx=20)
        rate_entry_ce = ctk.CTkEntry(tab_ce, width=300)
        rate_entry_ce.insert(0, str(self.db.get_rate("exchange_rate")))
        rate_entry_ce.pack(fill="x", padx=20, pady=(0, 15))

        #Result Preview
        preview_frame = ctk.CTkFrame(tab_ce, fg_color=self.colors["card"], corner_radius=8)
        preview_frame.pack(fill="x", padx=20, pady=15)

        result_text_ce = ctk.StringVar(value="Result: ---")
        ctk.CTkLabel(preview_frame, textvariable=result_text_ce, font=("Consolas", 14, "bold"), text_color=self.colors["success"]).pack(pady=15)

        # Exchange Button
        ctk.CTkButton(tab_ce, text="CONFIRM EXCHANGE", command=lambda: process_transaction("currency"),
                      fg_color=self.colors["accent"], hover_color="#154360",
                      font=("Segoe UI", 12, "bold"), height=40).pack(side="bottom", fill="x", padx=20, pady=20)
        
        # === TAB 2 : Bank Exchange ===
        ctk.CTkLabel(tab_bt, text="Amount to Move:", font=("Segoe UI", 12)).pack(anchor="w", pady=(10, 5), padx=20)
        amt_entry_bt = ctk.CTkEntry(tab_bt, width=300, placeholder_text="0.00")
        amt_entry_bt.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(tab_bt, text="Currency:", font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 5), padx=20)
        cur_combo_var_bt = ctk.StringVar(value="USD ($)")
        cur_combo_bt = ctk.CTkComboBox(tab_bt, variable=cur_combo_var_bt, values=["USD ($)", "Lira (LBP)"], state="readonly", width=300)
        cur_combo_bt.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(tab_bt, text="Direction:", font=("Segoe UI", 12)).pack(anchor="w", pady=(0, 5), padx=20)
        dir_combo_var_bt = ctk.StringVar(value="Cash -> Card")
        dir_combo_bt = ctk.CTkComboBox(tab_bt, variable=dir_combo_var_bt, values=["Cash -> Card", "Card -> Cash"], state="readonly", width=300)
        dir_combo_bt.pack(fill="x", padx=20, pady=(0, 15))

        # Transfer Button
        ctk.CTkButton(tab_bt, text="CONFIRM TRANSFER", command=lambda: process_transaction("transfer"), 
                      fg_color=self.colors["accent"], hover_color="#154360", 
                      font=("Segoe UI", 12, "bold"), height=40).pack(side="bottom", fill="x", padx=20, pady=20)

        def update_preview(event=None):
            try:
                amt_str = amt_entry_ce.get()
                rate_str = rate_entry_ce.get()

                if not amt_str or not rate_str:
                    result_text_ce.set("Result: ...")
                    return
                
                amount = float(amt_str)
                rate=float(rate_str)
                direction = dir_combo_ce.get()

                if direction == "USD -> LBP":
                    res = amount * rate
                    result_text_ce.set(f"Will receive: {res:,.0f} L.L")
                else:
                    res = amount / rate
                    result_text_ce.set(f"Will Receive: {res:,.2f} $")

            except ValueError:
                result_text_ce.set("Result: ...")

        def process_transaction(action_type):
            try:
                store = self.store_combo.get()
                today = datetime.now().strftime("%Y-%m-%d")

                if action_type == "currency":
                    amount = float(amt_entry_ce.get())
                    rate = float(rate_entry_ce.get())
                    direction = dir_combo_var_ce.get()
                    
                    if direction == "USD -> LBP":
                        converted_amt = round(amount * rate, 0)
                        cur_out = "USD ($)"
                        cur_in = "Lira (LBP)"
                    else:
                        converted_amt = round(amount / rate, 2)
                        cur_out = "Lira (LBP)"
                        cur_in = "USD ($)"
                    
                    cat_out = "Exchange Out"
                    cat_in = "Exchange In"
                    paym_out = "Cash"
                    paym_in = "Cash"

                elif action_type == "transfer":
                    amount = float(amt_entry_bt.get())
                    converted_amt = amount # Bank transfers are 1:1
                    cur_out = cur_combo_var_bt.get()
                    cur_in = cur_out
                    direction = dir_combo_var_bt.get()
                    
                    if direction == "Cash -> Card":
                        paym_out = "Cash"
                        paym_in = "Card"
                    else:
                        paym_out = "Card"
                        paym_in = "Cash"
                        
                    cat_out = "Bank Transfer Out"
                    cat_in = "Bank Transfer In"

                parent_id = self.db.add_transactions(
                    store, today, "Expense", cat_out, amount, cur_out, paym_out, parent_id=None
                )

                self.db.add_transactions(
                    store, today, "Income", cat_in, converted_amt, cur_in, paym_in, parent_id=parent_id
                )

                messagebox.showinfo("Success", "Transaction Recorded successfully!", parent=top)
                top.destroy()
                self.view_records()
            
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number.", parent=top)


        amt_entry_ce.bind("<KeyRelease>", update_preview)
        rate_entry_ce.bind("<KeyRelease>", update_preview)
        dir_combo_ce.configure(command=update_preview)

    def open_balances_window(self):
        top = ctk.CTkToplevel(self.root)
        top.title("All Branch Balances")
        top.geometry("750x600")
        top.grab_set()
        top.focus()

        ctk.CTkLabel(top, text="Current Balance Sheet", font=("Roboto Medium", 20), 
                 text_color=self.colors["accent"]).pack(pady=(20, 15))
        
        table_frame = ctk.CTkFrame(top, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        cols = ("Branch", "USD Cash", "USD Card", "LBP Cash", "LBP Card")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="none")

        tree.heading("Branch", text="Branch")
        tree.column("Branch", width=160, anchor="w")
        
        for col in cols[1:]:
            tree.heading(col, text=col)
            tree.column(col, width=130, anchor="e")

        

        # SCrollbar
        scrollbar = ctk.CTkScrollbar(table_frame, orientation="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscroll=scrollbar.set)

        tree.pack(fill="both", expand=True, side="left")

        # DATA PROCESSING LOGIC
        raw_data = self.db.get_balance_summary()

        branch_data = {}
        all_stores = self.db.get_store_names()


        for store in all_stores:
            branch_data[store] = {"USD ($)": {"Cash": 0, "Card": 0}, "Lira (LBP)": {"Cash": 0, "Card": 0}}


        for row in raw_data:
            store, curr, method, amount = row
            if store in branch_data:
                branch_data[store][curr][method] = amount

        grand_totals = [0, 0, 0, 0]

        for store in all_stores:
            d = branch_data[store]
            
            usd_cash = d["USD ($)"]["Cash"]
            usd_card = d["USD ($)"]["Card"]
            lbp_cash = d["Lira (LBP)"]["Cash"]
            lbp_card = d["Lira (LBP)"]["Card"]


            grand_totals[0] += usd_cash
            grand_totals[1] += usd_card
            grand_totals[2] += lbp_cash
            grand_totals[3] += lbp_card


            values = (
                store,
                f"${usd_cash:,.2f}",
                f"${usd_card:,.2f}",
                f"{lbp_cash:,.0f} L.L",
                f"{lbp_card:,.0f} L.L"
            )
            tree.insert("", "end", values=values)

        tree.insert("", "end", values=("TOTALS:", 
                                       f"${grand_totals[0]:,.2f}", 
                                       f"${grand_totals[1]:,.2f}", 
                                       f"{grand_totals[2]:,.0f} L.L", 
                                       f"{grand_totals[3]:,.0f} L.L"), 
                                       tags=("total_row",))
        
        tree.tag_configure("total_row", background=self.colors["accent"], foreground="white", font=("Segoe UI", 11, "bold"))

    def open_daily_reconciliation_window(self):
        # 1. Window Setup
        top = ctk.CTkToplevel(self.root)
        top.title("Daily Reconciliation")
        top.geometry("1100x700") 
        top.grab_set()
        top.focus()

        # --- Section 1: Header (Setup & Target) ---
        header_frame = ctk.CTkFrame(top, fg_color=self.colors["header"], height=120, corner_radius=0)
        header_frame.pack(fill="x")

        # Left Side: Selectors
        setup_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        setup_frame.pack(side="left", padx=20, pady=20)

        ctk.CTkLabel(setup_frame, text="Branch:", font=("Segoe UI", 12, "bold"), text_color="#bdc3c7").grid(row=0, column=0, sticky="w")

        self.recon_branch = ctk.CTkComboBox(setup_frame, values=self.db.get_store_names(), state="readonly", width=150)
        self.recon_branch.set(self.db.get_store_names()[0])
        self.recon_branch.grid(row=0, column=1, padx=10)

        ctk.CTkLabel(setup_frame, text="Date:", font=("Segoe UI", 12, "bold"), text_color="#bdc3c7").grid(row=1, column=0, sticky="w", pady=(10,0))

        self.recon_date = DateEntry(setup_frame, width=15, background="#1f538d", foreground='white', borderwidth=0, font=("Segoe UI", 12), date_pattern='yyyy-mm-dd')
        self.recon_date.grid(row=1, column=1, padx=10, pady=(10,0), ipady=5)

        # --- THE NEW BUTTONS SECTION ---
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.pack(side="left", padx=30)

        # Load Button
        ctk.CTkButton(btn_frame, text="📥 Load Target", fg_color="#34495e", hover_color="#2c3e50", font=("Segoe UI", 12, "bold"), width=120,
                  command=self.load_daily_sales).pack(pady=5)

        # NEW Save Button
        ctk.CTkButton(btn_frame, text="💾 Save Target", fg_color="#27ae60", hover_color="#219a52", font=("Segoe UI", 12, "bold"), width=120,
                  command=self.save_daily_sales_target).pack(pady=5)


        # Right Side: The Target Input
        target_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        target_frame.pack(side="right", padx=30, pady=20)

        ctk.CTkLabel(target_frame, text="Expected Sales (LBP):", font=("Segoe UI", 14, "bold"), text_color="#f1c40f").pack(anchor="e")
        
        self.target_entry = ctk.CTkEntry(target_frame, font=("Consolas", 18, "bold"), width=200, justify="right")
        self.target_entry.pack(anchor="e", pady=(5,0))
        
        # Bind to recalculate
        self.target_entry.bind("<KeyRelease>", self.recalc_sales_difference)

        # --- Section 2: The Envelopes (The Count) ---
        envelopes_container = ctk.CTkFrame(top, fg_color="transparent")
        envelopes_container.pack(fill="both", expand=True, padx=20, pady=20)

        # FIX 2: Create the dictionary that your logic is looking for
        self.recon_inputs = {"env1": {}, "env2": {}}

        def build_envelope_grid(parent, title, key):
            frame = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=15)
            frame.pack(side="left", fill="both", expand=True, padx=10)

            ctk.CTkLabel(frame, text=title, font=("Roboto Medium", 16), text_color="white").grid(row=0, column=0, columnspan=2, pady=(15,15))

            ctk.CTkLabel(frame, text="Currency", font=("Segoe UI", 11, "bold"), text_color="#7f8c8d").grid(row=1, column=0, sticky="w", padx=20, pady=(0,10))
            ctk.CTkLabel(frame, text="Amount", font=("Segoe UI", 11, "bold"),  text_color="#7f8c8d").grid(row=1, column=1, sticky="w", padx=20, pady=(0,10))

            rows = [
                ("USD Cash", "usd_cash"),
                ("USD Card", "usd_card"),
                ("LBP Cash", "lbp_cash"),
                ("LBP Card", "lbp_card")
            ]

            for i, (label_text, tag) in enumerate(rows):
                ctk.CTkLabel(frame, text=label_text, font=("Segoe UI", 12)).grid(row=i+2, column=0, pady=10, padx=20, sticky="w")
                
                entry = ctk.CTkEntry(frame, font=("Segoe UI", 12), width=180, justify="right", placeholder_text="0.00")
                entry.grid(row=i+2, column=1, pady=10, padx=10)
                
                # FIX 3: Bind to the correct function name
                entry.bind("<KeyRelease>", self.recalc_sales_difference)

                # Store the widget so your logic can find it!
                self.recon_inputs[key][tag] = entry

        build_envelope_grid(envelopes_container, "✉️ Envelope 1", "env1")
        build_envelope_grid(envelopes_container, "✉️ Envelope 2", "env2")

        # --- Section 3: The Footer (Verdict & Action) ---
        footer_frame = ctk.CTkFrame(top, fg_color=self.colors["header"], height=100, corner_radius=0)
        footer_frame.pack(fill="x", side="bottom")

        results_box = ctk.CTkFrame(footer_frame, fg_color="transparent")
        results_box.pack(side="left", padx=40, pady=20)

        self.lbl_total_counted = ctk.CTkLabel(results_box, text="Total Counted: 0 LBP", font=("Segoe UI", 14), text_color="#bdc3c7")
        self.lbl_total_counted.pack(anchor="w")

        self.lbl_difference = ctk.CTkLabel(results_box, text="Difference: 0 LBP", font=("Segoe UI", 20, "bold"), text_color="white")
        self.lbl_difference.pack(anchor="w")

        actions_box = ctk.CTkFrame(footer_frame, fg_color="transparent")
        actions_box.pack(side="right", padx=40, pady=20)

        self.apply_tax_var = ctk.IntVar(value=1)
        ctk.CTkCheckBox(actions_box, text="Apply Main Taxes", variable=self.apply_tax_var, font=("Segoe UI", 12)).pack(anchor="e", pady=(0,15))

        # FIX 4: Bind button to 'submit_sale'
        self.btn_recon_confirm = ctk.CTkButton(actions_box, text="CONFIRM & POST", fg_color="#7f8c8d", text_color="white", 
                                           font=("Segoe UI", 14, "bold"), width=200, height=45,  state="disabled",
                                           command=self.submit_sale)
        self.btn_recon_confirm.pack(anchor="e")

    def load_daily_sales(self):
        branch_name = self.recon_branch.get()
        date = self.recon_date.get()

        amount = self.db.get_daily_sale(branch_name, date)

        self.target_entry.delete(0, tk.END)

        if amount > 0:
            self.target_entry.insert(0, f"{amount:.0f}")
        
        self.recalc_sales_difference()

    def save_daily_sales_target(self):
        branch = self.recon_branch.get()
        date = self.recon_date.get()
        
        try:
            val_str = self.target_entry.get().replace(",", "")
            if not val_str:
                messagebox.showwarning("Warning", "Please enter a target amount first.")
                return
                
            amount = float(val_str)
            
            self.db.save_daily_sale(branch, date, amount)
            
            messagebox.showinfo("Saved", f"Target of {amount:,.0f} LBP saved for {branch} on {date}.")

            self.recalc_sales_difference()
            
        except ValueError:
            messagebox.showerror("Error", "Invalid Number")

    def recalc_sales_difference(self, event=None):
        def get_val(entry_widget):
            try:
                val = entry_widget.get()
                if not val: return 0.0
                return float(val.replace(",", ""))
            except ValueError:
                return 0.0

        real_amount = get_val(self.target_entry)

        entered_amount = 0
        rate = self.db.get_rate("exchange_rate")

        for i in range(1,3):
            usd_cash = get_val(self.recon_inputs[f"env{i}"]["usd_cash"])
            LBP_cash = get_val(self.recon_inputs[f"env{i}"]["lbp_cash"])
            usd_card = get_val(self.recon_inputs[f"env{i}"]["usd_card"])
            LBP_card = get_val(self.recon_inputs[f"env{i}"]["lbp_card"])
            total_env = LBP_cash + LBP_card + ((usd_cash + usd_card) * rate)
            entered_amount += total_env

        self.lbl_total_counted.configure(text=f"Total Counted: {entered_amount:,.0f} L.L")

        difference = real_amount - entered_amount

        self.lbl_difference.configure(text=f"Difference: {difference:,.0f} L.L")

        if abs(difference) < 100000:
            self.lbl_difference.configure(text_color="#27ae60")
            self.btn_recon_confirm.configure(state="normal", fg_color="#27ae60", hover_color="#27ae60")
        else :
            self.lbl_difference.configure(text_color="#c0392b")
            self.btn_recon_confirm.configure(state="normal", fg_color="#c0392b", hover_color="#e74c3c")

    def submit_sale(self):
        branch = self.recon_branch.get()
        date = self.recon_date.get()
        
        try:
            target_val = float(self.target_entry.get().replace(",", ""))
            self.db.save_daily_sale(branch, date, target_val)
        except ValueError:
            pass

        diff_text = self.lbl_difference.cget("text")
        if "Difference: 0" not in diff_text and "Difference: -0" not in diff_text:
             if not messagebox.askyesno("Discrepancy Warning", f"The totals do not match the target.\n\n{diff_text}\n\nSubmit anyway?"):
                 return

        saved_count = 0
        
        main_rate = self.db.get_rate("main_rate")
        tva_rate = self.db.get_rate("tva_rate")
        comm_rate = self.db.get_rate("comm_rate")
        apply_main = self.apply_tax_var.get()

        money_types = [
            ("usd_cash", "USD ($)", "Cash"),
            ("usd_card", "USD ($)", "Card"),
            ("lbp_cash", "Lira (LBP)", "Cash"),
            ("lbp_card", "Lira (LBP)", "Card")
        ]

        for i in range(1, 3):
            env_key = f"env{i}"
            
            for key, curr, method in money_types:
                try:
                    widget = self.recon_inputs[env_key][key]
                    val_str = widget.get().replace(",", "")
                    
                    if not val_str: continue
                    
                    amount = float(val_str)
                    if amount <= 0: continue


                    main_id = self.db.add_transactions(branch, date, "Income", "Sales", amount, curr, method)
                    
                    val_tva = round(amount * (tva_rate / 100), 2)
                    self.db.add_transactions(branch, date, "Expense", f"TVA ({tva_rate:g}%)", val_tva, curr, method, parent_id=main_id)
                    self.db.add_transactions("TVA Account", date, "Income", f"from {branch}", val_tva, curr, method, parent_id=main_id)

                    if apply_main == 1:
                        val_main = round(amount * (main_rate / 100), 2)
                        self.db.add_transactions(branch, date, "Expense", f"Main ({main_rate:g}%)", val_main, curr, method, parent_id=main_id)
                        self.db.add_transactions("Main Vault", date, "Income", f"from {branch}", val_main, curr, method, parent_id=main_id)

                    if method == "Card":
                        val_comm = round(amount * (comm_rate / 100), 2)
                        self.db.add_transactions(branch, date, "Expense", f"Card Commission ({comm_rate:g}%)", val_comm, curr, method, parent_id=main_id)
                        self.db.add_transactions("Bank Commission", date, "Income", f"from {branch}", val_comm, curr, method, parent_id=main_id)

                    saved_count += 1

                except ValueError:
                    continue

        if saved_count > 0:
            messagebox.showinfo("Success", f"Posted {saved_count} sales records!")
            self.view_records()
        else:
            messagebox.showwarning("Warning", "No amounts were entered.")



    def toggle_category_state(self, choice=None):
        current_type = self.type_combo.get()
        current_store = self.store_combo.get()

        if current_type == "Income":
            new_values = ["Sales", "Investment"]
            self.cat_combo.configure(values=new_values, state="readonly")
            self.cat_combo.set(new_values[0])
        else:
            if current_store in self.system_accounts:

                if current_store == "Main Vault":
                    new_values = self.main_category_list
                    self.cat_combo.configure(values = new_values, state="readonly")
                    self.cat_combo.set(new_values[0])
                
                else:
                    self.cat_combo.configure(values =[] , state="normal")
                    self.cat_combo.set("")

            else:
                new_values = self.category_list
                self.cat_combo.configure(values=new_values, state="readonly")
                self.cat_combo.set(new_values[0])

    def reset_filters(self):
        self.filter_cat.set("All")
        self.filter_type.set("All")
        self.date_from.delete(0, tk.END)
        self.date_to.delete(0, tk.END)
        self.filter_curr.set("All")
        self.filter_paym.set("All")
        self.view_records()

    def delete_record(self):
        selected_item = self.tree.selection()

        if not selected_item:
            messagebox.showwarning("Warning", "Please select a row to delete")
            return
        
        confirm = messagebox.askyesno("Confirm", "Are you sure you want to delete this entry ?")
        if confirm:
            row_data = self.tree.item(selected_item)['values']
            record_id = row_data[0]

            self.db.delete_smart_chain(record_id)

            self.view_records()
            messagebox.showinfo("Succes", "Record and linked taxes deleted")

    def add_records(self):
        store = self.store_combo.get()
        t_type = self.type_combo.get()
        cat = self.cat_combo.get()
        amt = self.amount_entry.get()
        cur = self.cur_combo.get()
        paym = self.paym_combo.get()
        date_val = self.date_entry.get()
        desc = self.desc_entry.get()

        if not date_val.strip():
            date_val = datetime.now().strftime("%Y-%m-%d")

        if not cat or not amt:
            messagebox.showerror("Error", "Please fill all the fields")
            return
        
        try:
            val = float(amt)
            today = date_val

            main_id = self.db.add_transactions(store, today, t_type, cat, val, cur, paym, parent_id = None, description=desc)

            if cat == "Cost of goods" and t_type == "Expense":
                freight_rate = self.db.get_rate("freight_rate")
                self.db.add_transactions("Cost of goods", today, "Income", f"from {store}", val, cur, paym, parent_id = main_id)
                amt_freight = round(val * (freight_rate / 100), 2)
                self.db.add_transactions(store, today, "Expense", "Freight", amt_freight, cur, paym, parent_id = main_id)
                self.db.add_transactions("Freight", today, "Income", f"from {store}", amt_freight, cur, paym, parent_id = main_id)

            if cat == "Main" and t_type == "Expense" :
                self.db.add_transactions("Main Vault", today, "Income", f"from {store}", val, cur, paym, parent_id = main_id)

            if t_type == "Income" and cat == "Sales":
                main_rate = self.db.get_rate("main_rate")
                tva_rate = self.db.get_rate("tva_rate")
                card_rate = self.db.get_rate("comm_rate")
                main_skip = self.no_main_var.get()

                if main_skip == 0:
                    amount_main = round(val * (main_rate / 100), 2)
                    self.db.add_transactions(store, today, "Expense", f"Main ({main_rate:g}%)", amount_main, cur, paym, parent_id = main_id)
                    self.db.add_transactions("Main Vault", today, "Income", f"from {store}", amount_main, cur, paym, parent_id = main_id)

                amount_tva = round(val * (tva_rate / 100), 2)
                self.db.add_transactions(store, today, "Expense", f"TVA ({tva_rate:g}%)", amount_tva, cur, paym, parent_id = main_id)
                self.db.add_transactions("TVA Account", today, "Income", f"from {store}", amount_tva, cur, paym, parent_id = main_id)

                if paym == "Card":
                    amount_card = round(val * (card_rate / 100), 2)
                    self.db.add_transactions(store, today, "Expense", f"Card Commission ({card_rate:g}%)", amount_card, cur, paym, parent_id = main_id)
                    self.db.add_transactions("Bank Commission", today, "Income", f"from {store}", amount_card, cur, paym, parent_id = main_id)

            messagebox.showinfo("Succes", "Transaction Saved!")

            self.amount_entry.delete(0, tk.END)
            self.date_entry.set_date(datetime.now())
            self.desc_entry.delete(0, tk.END)

            self.type_combo.current(0)
            self.toggle_category_state()

            self.view_records()
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number")

    
    #Important for tree display, and filters
    def view_records(self):
        store_name = self.store_combo.get()

        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.get_transactions(store_name)

        f_type = self.filter_type.get()
        f_cat = self.filter_cat.get()
        f_curr = self.filter_curr.get()
        f_paym = self.filter_paym.get()
        start_date = self.date_from.get()
        end_date = self.date_to.get()

        total_usd_cash = 0
        total_usd_card = 0
        total_lbp_cash = 0
        total_lbp_card = 0

        self.tree.tag_configure("oddrow", background="#2b2b2b", foreground="white")
        self.tree.tag_configure("evenrow", background="#383838", foreground="white")

        count = 0

        self.current_data = []

        for row in rows:
            t_type = row[2]
            categ = row[3]
            date = row[1]
            curr = row[5]
            paym = row[6]

            if f_type != "All" and t_type != f_type:
                continue

            if start_date and date < start_date:
                continue

            if end_date and date > end_date:
                continue

            if f_curr != "All" and curr != f_curr:
                continue

            if f_paym != "All" and paym != f_paym:
                continue

            if f_cat != "All" and f_cat.strip() != "":
                
                if f_cat == "Exchange In/Out":
                    if categ not in ["Exchange In", "Exchange Out"]:
                        continue
                        
                elif f_cat == "Bank Transfer In/Out":
                    if categ not in ["Bank Transfer Out", "Bank Transfer In"]:
                        continue        
                else:
                    is_fuzzy_match = f_cat.lower() in categ.lower()
                    
                    is_from_match = (store_name in self.system_accounts) and (categ == f"from {f_cat}")
                    
                    if not (is_fuzzy_match or is_from_match):
                        continue

            

            self.current_data.append(row)
            if count < 300:
                if count % 2 == 0:
                    self.tree.insert("", "end", values=row, tags=("evenrow",))
                else:
                    self.tree.insert("", "end", values=row, tags=("oddrow",))
            
            count += 1

            try:
                amount = float(row[4])
                curr = row[5]
                paym = row[6]

                if curr == "USD ($)":
                    if paym == "Cash":
                        if t_type == "Income" : total_usd_cash += amount
                        else : total_usd_cash -= amount
                    elif paym == "Card":
                        if t_type == "Income" : total_usd_card += amount
                        else : total_usd_card -= amount
                elif curr == "Lira (LBP)":
                    if paym == "Cash":
                        if t_type == "Income" : total_lbp_cash += amount
                        else : total_lbp_cash -= amount
                    elif paym == "Card":
                        if t_type == "Income" : total_lbp_card += amount
                        else : total_lbp_card -= amount
            except ValueError:
                pass


        report = f"USD Cash: ${total_usd_cash:,.2f} | USD Card ${total_usd_card:,.2f}\n LBP Cash: {total_lbp_cash:,.0f} L.L | LBP Card: {total_lbp_card:,.0f} L.L"
        self.status_label.configure(text=report)
        current_rate = self.db.get_rate("exchange_rate")

        grand_total_usd = total_usd_cash + (total_lbp_cash / current_rate) + total_usd_card + (total_lbp_card / current_rate) if current_rate > 0 else 0
        self.grand_total_label.configure(text=f"Grand Total: ${grand_total_usd:,.2f}")


    def update_filter_dropdown(self, event=None):
        current_store = self.store_combo.get()
        f_type = self.filter_type.get()

        new_values = ["All"]

        extra_filters = ["Exchange In/Out", "Bank Transfer In/Out"]

        combo_state = "readonly"

        if current_store in self.system_accounts:
            if f_type == "Income":
                all_branches = self.db.get_store_names()
                real_branches = [s for s in all_branches if s not in self.system_accounts]
                new_values += real_branches

            elif f_type == "Expense":
                if current_store == "Main Vault":
                    new_values += self.main_category_list
                else:
                    combo_state = "normal"

            else :
                all_branches = self.db.get_store_names()
                real_branches = [s for s in all_branches if s not in self.system_accounts]
                if current_store == "Main Vault":
                    new_values += self.main_category_list + real_branches
                else:
                    new_values += real_branches
                    combo_state = "normal"
        

        else :
            if f_type == "Income":
                new_values += ["Sales", "Investment"] + extra_filters
            elif f_type == "Expense":
                new_values += self.category_list + extra_filters
            else:
                new_values += self.category_list + ["Sales", "Investment"] + extra_filters

        self.filter_cat.configure(values=new_values, state=combo_state)
        self.filter_cat.set(new_values[0])

        self.view_records()
    
    def export_to_excel(self):
        filename = filedialog.asksaveasfilename(
            initialdir="/",
            title="Save as",
            filetypes=(("CSV File", "*csv"), ("All Files", "*.*")),
            defaultextension=".csv"
        )

        if not filename:
            return
        
        store_name = self.store_combo.get()
        rows = self.current_data

        if not rows:
            messagebox.showwarning("Warning", "No data to export")
            return

        try:
            with open(filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                headers = ["ID", "Date", "Type", "Category", "Amount", "Currency", "Method", "Description"]
                writer.writerow(headers)

                writer.writerows(rows)

            messagebox.showinfo("Succes", f"Data exported to {filename}")   
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file: {e}")

    def setup_styles(self):
        style = ttk.Style()

        style.theme_use("default")

        style.configure("Treeview", 
                        background="#2b2b2b",
                        foreground="white",
                        fieldbackground="#2b2b2b",
                        rowheight=35, 
                        font=("Segoe UI", 11),
                        borderwidth=0)
        
        
        style.configure("Treeview.Heading", 
                        font=("Segoe UI", 11, "bold"),
                        background="#1a1a1a",
                        foreground="white",
                        relief="flat")
        
        style.map("Treeview.Heading",
                  background=[('active', '#333333')])
        
        
        style.map("Treeview",
                  background=[('selected', '#1f538d')],
                  foreground=[('selected', 'white')])


if __name__ == "__main__":
    root = ctk.CTk()
    app = StoreApp(root)
    root.mainloop()
    