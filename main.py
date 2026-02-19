import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
from tkcalendar import DateEntry

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

        self.root.state("zoomed")
        self.root.geometry("900x600")

        self.db = DatabaseManager()

        #Color dictionnary
        self.colors = {
            "bg": "#f0f2f5",         
            "header": "#2c3e50",      
            "text": "#ffffff",        
            "accent": "#2980b9",     
            "success": "#27ae60",    
            "danger": "#c0392b",      
            "white": "#ffffff"
        }

        self.root.configure(bg=self.colors["bg"])

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
        ]

        self.main_category_list = [
            "Upgrades",
            "Salaries",
            "Bank Fees",
            "Audit",
            "Bags & EAS",
            "Social Media",
            "Electricity & Phone",
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

    def setup_header(self):
        #the frame for the header
        header_frame = tk.Frame(self.root,bg =self.colors["header"], height=60)
        header_frame.pack(fill="x")

        #Now the Title on top of the page
        title_label = tk.Label(header_frame, text="Select Branch", bg=self.colors["header"], font=("Segoe UI", 18, "bold"), fg="white")
        title_label.pack(side=tk.LEFT, padx=20, pady=10)

        settings_btn = tk.Button(header_frame, text="⚙ Settings", bg=self.colors["accent"], fg="white", 
                                 font=("Segoe UI", 10, "bold"), relief="raised", bd=1, activebackground="#3498db", cursor="hand2",
                                 command=self.open_settings_window)
        settings_btn.pack(side=tk.RIGHT, padx=20, pady=10)

        all_stores = self.db.get_store_names()

        #Now under it we want to branch dropdown menu
        self.store_var = tk.StringVar()
        self.store_combo = ttk.Combobox(header_frame, textvariable=self.store_var, values=all_stores, state="readonly")

        self.store_combo.current(0)
        self.store_combo.pack(side=tk.RIGHT, padx=20, pady=10)

        def on_branch_change(event):
            self.toggle_category_state()
            self.update_filter_dropdown()

            try:
                self.no_main_var.set(0)
            except AttributeError:
                pass

        self.store_combo.bind("<<ComboboxSelected>>", on_branch_change)

    def setup_inputs(self):
        master_frame = tk.Frame(self.root, bg=self.colors["bg"])
        master_frame.pack(fill="x", padx=20, pady=15)

        #Input side 
        input_frame = tk.LabelFrame(master_frame, text="New Transaction")
        input_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0,10))

        tk.Label(input_frame, text="Date", bg=self.colors["bg"]).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.date_entry = DateEntry(input_frame, width=12, background="darkblue", foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(input_frame, text="Type", bg=self.colors["bg"]).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(input_frame, textvariable=self.type_var, values=["Income","Expense"], state="readonly", width=12)
        self.type_combo.current(0)
        self.type_combo.grid(row=0, column=3, padx=5, pady=5)

        self.type_combo.bind("<<ComboboxSelected>>", self.toggle_category_state)

        tk.Label(input_frame, text="Category", bg=self.colors["bg"]).grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.cat_var = tk.StringVar()
        self.cat_combo = ttk.Combobox(input_frame, textvariable=self.cat_var, values=self.category_list, state = "readonly", width=15)
        self.cat_combo.current(0)
        self.cat_combo.grid(row=0, column=5, padx=5, pady=5)

        tk.Label(input_frame, text="Amount ($)", bg=self.colors["bg"]).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.amount_entry = tk.Entry(input_frame, width=15)
        self.amount_entry.grid(row=1, column=1, padx=5, pady=5)

        self.amount_entry.bind('<Return>', lambda event: self.add_records())

        tk.Label(input_frame, text="Currency", bg=self.colors["bg"]).grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.currency_var = tk.StringVar()
        self.cur_combo = ttk.Combobox(input_frame, textvariable=self.currency_var, values=["USD ($)", "Lira (LBP)"], state="readonly", width=12)
        self.cur_combo.current(0)
        self.cur_combo.grid(row=1, column=3, padx=5, pady=5)

        tk.Label(input_frame, text="Payment Method", bg=self.colors["bg"]).grid(row=1, column=4, padx=5, pady=5, sticky="w")
        self.paym_var = tk.StringVar()
        self.paym_combo = ttk.Combobox(input_frame, textvariable=self.paym_var, values=["Cash", "Card"], state="readonly", width=12)
        self.paym_combo.current(0)
        self.paym_combo.grid(row=1, column=5, padx=5, pady=5) 

        tk.Label(input_frame, text="Description (Opt):", bg=self.colors["bg"]).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.desc_entry = tk.Entry(input_frame, width=35)
        self.desc_entry.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        self.no_main_var = tk.IntVar()
        no_main_chk = tk.Checkbutton(input_frame, text="Skip Main", variable=self.no_main_var, bg=self.colors["bg"], activebackground=self.colors["bg"])
        no_main_chk.grid(row=2, column=4, columnspan=2, sticky="w", padx=5)

        #Input buttons section
        input_btn_frame = tk.Frame(input_frame, background=self.colors["bg"])
        input_btn_frame.grid(row=3, column=0, columnspan=6, pady=15, sticky="ew")

        # To give both buttons equal sapce
        input_btn_frame.columnconfigure(0, weight=1)
        input_btn_frame.columnconfigure(1, weight=1)

        add_btn = tk.Button(input_btn_frame, text="+ Add Record", bg=self.colors["success"], fg="white", font=("Segoe UI", 10, "bold"), cursor="hand2", relief="flat",command=self.add_records)
        add_btn.grid(row=0, column=0, sticky="ew", padx=(10, 5), ipady=5)

        exchange_btn = tk.Button(input_btn_frame, text="Exchange", font=("Segoe UI", 10, "bold"), bg="#e67e22", fg="white", cursor="hand2", relief="flat",command=self.open_exchange_window)
        exchange_btn.grid(row=0, column=1, sticky="ew", padx=(5, 10), ipady=5)

        #filter side
        filter_frame = ttk.LabelFrame(master_frame, text="Filters")
        filter_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=(10,0))

        tk.Label(filter_frame, text="Filter Type:", bg=self.colors["bg"]).grid(row=0, column=0, padx=5, pady=10)
        self.filter_type_var = tk.StringVar()
        self.filter_type = ttk.Combobox(filter_frame, textvariable="self.filter_type_var", values=["All", "Income", "Expense"], state="readonly", width=10)
        self.filter_type.current(0)
        self.filter_type.grid(row=0, column=1, padx=5)
        self.filter_type.bind("<<ComboboxSelected>>", self.update_filter_dropdown)

        tk.Label(filter_frame, text="Filter Category:", bg=self.colors["bg"]).grid(row=0, column=2, padx=5, pady=10)
        full_cat_list = ["All", "Cash Flow", "Exchange In/Out"] + self.category_list
        self.filter_cat_var = tk.StringVar()
        self.filter_cat = ttk.Combobox(filter_frame, textvariable="self.filter_cat_var", values= full_cat_list, state="readonly", width=15)
        self.filter_cat.current(0)
        self.filter_cat.grid(row=0, column=3, padx=5)

        tk.Label(filter_frame, text="Currency:", bg=self.colors["bg"]).grid(row=1, column=0, padx=5, pady=5)
        self.filter_curr_var = tk.StringVar()
        self.filter_curr = ttk.Combobox(filter_frame, textvariable="self.filter_curr_var", values= ["All", "USD ($)", "Lira (LBP)"], state="readonly", width=10)
        self.filter_curr.current(0)
        self.filter_curr.grid(row=1, column=1, padx=5)
        self.filter_curr.bind("<<ComboboxSelected>>", lambda e: self.view_records())

        tk.Label(filter_frame, text="Method:", bg=self.colors["bg"]).grid(row=1, column=2, padx=5, pady=5)
        self.filter_paym_var = tk.StringVar()
        self.filter_paym = ttk.Combobox(filter_frame, textvariable="self.filter_paym_var", values= ["All", "Cash", "Card"], state="readonly", width=15)
        self.filter_paym.current(0)
        self.filter_paym.grid(row=1, column=3, padx=5)
        self.filter_paym.bind("<<ComboboxSelected>>", lambda e: self.view_records())

        tk.Label(filter_frame, text="From:", bg=self.colors["bg"]).grid(row=2, column=0, padx=5, pady=5)
        self.date_from = DateEntry(filter_frame, width=12, background="darkblue", foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.date_from.delete(0, "end")
        self.date_from.grid(row=2, column=1, padx=5)

        tk.Label(filter_frame, text="To:", bg=self.colors["bg"]).grid(row=2, column=2, padx=5, pady=5)
        self.date_to = DateEntry(filter_frame, width=12, background="darkblue", foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.date_to.delete(0, "end")
        self.date_to.grid(row=2, column=3, padx=5)

        #filter Buttons section
        filter_btn_frame = tk.Frame(filter_frame, )
        filter_btn_frame.grid(row=3, column=0, columnspan=4, pady=10)

        tk.Button(filter_btn_frame, text="Apply Filter", bg="#2c3e50", fg="white", command=self.view_records).pack(side=tk.LEFT, padx=5)
        tk.Button(filter_btn_frame, text="Reset", command = self.reset_filters).pack(side=tk.LEFT, padx=5)

        self.filter_cat.bind("<<ComboboxSelected>>", lambda e: self.view_records())


    def setup_table(self):
        main_content = tk.Frame(self.root, bg=self.colors["bg"])
        main_content.pack(fill="both", expand=True, padx=20, pady=(0,20))


        tree_frame = tk.Frame(main_content)
        tree_frame.pack(fill="both", expand=True)

        cols = ("ID", "Date", "Type", "Category", "Amount", "Currency", "Payment Method", "Description")

        visible_cols = ("Date", "Type", "Category", "Amount", "Currency", "Payment Method", "Description")

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", displaycolumns=visible_cols)

        self.tree.column("Date", width=90, anchor=tk.CENTER)
        self.tree.column("Type", width=70, anchor=tk.CENTER)
        self.tree.column("Category", width=130, anchor=tk.W)
        self.tree.column("Description", width=200, anchor=tk.W)
        self.tree.column("Amount", width=90, anchor=tk.E)  
        self.tree.column("Currency", width=70, anchor=tk.CENTER)
        self.tree.column("Payment Method", width=80, anchor=tk.CENTER)
        

        for col in visible_cols:
            self.tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill="y")
        
        self.tree.pack(fill="both", expand=True)

        self.tree.bind('<Delete>', lambda event: self.delete_record())


        bottom_frame = tk.Frame(main_content, bg=self.colors["bg"])
        bottom_frame.pack(fill="x", pady=10)

        export_btn = tk.Button(bottom_frame, text="Export to Excel", bg=self.colors["accent"], fg="white", command=self.export_to_excel)
        export_btn.pack(side=tk.LEFT, padx=5)

        #He placeholder ma bt bayyin b bayyin mahala l hateto b show records and __init__ he bas just to be safe
        self.status_label = tk.Label(bottom_frame, text="Loading...", font=("Segoe UI", 12, "bold"), bg=self.colors["bg"], justify=tk.RIGHT)
        self.status_label.pack(side=tk.RIGHT)

        #Right click menu part 
        self.context_menu = tk.Menu(self.root, tearoff=0)

        self.context_menu.add_command(label="Edit Record", command=self.open_edit_window)

        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Record", command=self.delete_record)
        self.tree.bind("<Button-3>", self.show_context_menu)

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

        edit_win = tk.Toplevel(self.root)
        edit_win.title("Edit Record")
        edit_win.geometry("300x400")

        tk.Label(edit_win, text="Date:").pack(pady=5)
        date_entry = DateEntry(edit_win, width=12, date_pattern='yyyy-mm-dd')
        date_entry.set_date(old_date)
        date_entry.pack()

        valid_categories = []
        store = self.store_combo.get()
        if old_type == "Income":
                    valid_categories = ["Cash Flow"]
        else:
            if store == "Main Vault":
                valid_categories = self.main_category_list
            else:
                valid_categories = self.category_list

        tk.Label(edit_win, text="Category:").pack(pady=5)
        cat_entry = ttk.Combobox(edit_win, values=valid_categories, state="readonly")
        cat_entry.set(old_cat)
        cat_entry.pack()

        tk.Label(edit_win, text="Description:").pack(pady=5)
        desc_entry = tk.Entry(edit_win, width=30)
        desc_entry.insert(0, old_desc)
        desc_entry.pack()

        tk.Label(edit_win, text="Amount:").pack(pady=5)
        amt_entry = tk.Entry(edit_win)
        amt_entry.insert(0, str(old_amt))
        amt_entry.pack()

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

                messagebox.showinfo("Success", "Record Updated!")
                edit_win.destroy()
                self.view_records()
            except ValueError:
                messagebox.showerror("Error", "Amount must be a number")

        tk.Button(edit_win, text="Save Changes", command=save_changes, bg=self.colors["success"], fg="white").pack(pady=20)

    def open_settings_window(self):
        top = tk.Toplevel(self.root)
        top.title("Configure Rates")
        top.geometry("300x350")

        top.configure(bg=self.colors["bg"])

        tk.Label(top, text="Update Tax Rates", font=("Segoe UI", 14, "bold"), 
                 bg=self.colors["bg"], fg=self.colors["header"]).pack(pady=15)
        
        form_frame = tk.Frame(top, bg=self.colors["bg"])
        form_frame.pack(pady=10)

        def make_row(row, label_text, key):
            
            tk.Label(form_frame, text=label_text, font=("Segoe UI", 10), 
                     bg=self.colors["bg"], fg="#2c3e50", anchor="w").grid(row=row, column=0, padx=15, pady=8, sticky="w")
            
            
            entry = tk.Entry(form_frame, width=10, font=("Segoe UI", 10), justify="center", bd=1, relief="solid")
            
            
            entry.grid(row=row, column=1, padx=15, pady=8)
            
            
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

        
        save_btn = tk.Button(top, text="Save Changes", command=save, 
                             bg=self.colors["success"], fg="white", font=("Segoe UI", 11, "bold"), 
                             width=20, relief="flat", cursor="hand2")
        save_btn.pack(pady=20)

    def open_exchange_window(self):
        top = tk.Toplevel(self.root)
        top.title("Exchange currency")
        top.geometry("380x500")
        top.configure(bg=self.colors["bg"])
        top.resizable(False, False)

        notebook = ttk.Notebook(top)
        notebook.pack(fill="both", expand=True, padx=15, pady=15)

        currency_exchange_frame = tk.Frame(notebook, bg=self.colors["bg"])
        bank_transfer_frame = tk.Frame(notebook, bg=self.colors["bg"])

        notebook.add(currency_exchange_frame, text="Currency Exchange")
        notebook.add(bank_transfer_frame, text="Bank Transfer")

        tk.Label(currency_exchange_frame, text="Currency Exchange", font=("Segoe UI", 14, "bold"), 
                 bg=self.colors["header"], fg="white").pack(fill="x", pady=(0, 15), ipady=10)

        pad_frame_ce = tk.Frame(currency_exchange_frame, bg=self.colors["bg"])
        pad_frame_ce.pack(fill="both", expand=True, padx=20)

        tk.Label(pad_frame_ce, text="Amount to Change:", font=("Segoe UI", 11), bg=self.colors["bg"]).pack(anchor="w", pady=(0,5))
        amt_entry_ce = tk.Entry(pad_frame_ce, width=20, font=("Segoe UI", 12), bd=2, relief="flat")
        amt_entry_ce.pack(fill="x", ipady=5)

        tk.Label(pad_frame_ce, text="Direction:", font=("Segoe UI", 11), bg=self.colors["bg"]).pack(anchor="w", pady=(15,5))
        dir_combo_var_ce = tk.StringVar()
        dir_combo_ce = ttk.Combobox(pad_frame_ce, textvariable=dir_combo_var_ce, values=["USD -> LBP", "LBP -> USD"], state="readonly", font=("Segoe UI", 11))
        dir_combo_ce.current(0)
        dir_combo_ce.pack(fill="x", ipady=4)

        tk.Label(pad_frame_ce, text="Exchange Rate:", font=("Segoe UI", 11), bg=self.colors["bg"]).pack(anchor="w", pady=(15,5))
        rate_entry_ce = tk.Entry(pad_frame_ce , font=("Segoe UI", 12), width=20, bd=2, relief="flat")
        rate_entry_ce.insert(0, self.db.get_rate("exchange_rate"))
        rate_entry_ce.pack(fill="x", ipady=5)

        result_frame_ce = tk.Frame(pad_frame_ce, bg="#dfe6e9", bd=1, relief="solid")
        result_frame_ce.pack(fill="x", pady=25)

        result_text_ce = tk.StringVar()
        result_text_ce.set("---")
        tk.Label(result_frame_ce, textvariable=result_text_ce, font=("Consolas", 14, "bold"), bg="#dfe6e9", fg="#2d3436").pack(pady=10)

        exchange_btn_ce = tk.Button(currency_exchange_frame, text="CONFIRM EXCHANGE", command=lambda: process_transaction("transfer"), bg=self.colors["accent"], fg="white", font=("Segoe UI", 12, "bold"), relief="flat", cursor="hand2")
        exchange_btn_ce.pack(side=tk.BOTTOM, fill="x", pady=20, padx=20, ipady=10)

        tk.Label(bank_transfer_frame, text="Bank Transfer", font=("Segoe UI", 14, "bold"), 
                 bg=self.colors["header"], fg="white").pack(fill="x", pady=(0, 15), ipady=10)

        pad_frame_bt = tk.Frame(bank_transfer_frame, bg=self.colors["bg"])
        pad_frame_bt.pack(fill="both", expand=True, padx=20)

        tk.Label(pad_frame_bt, text="Amount to Move:", font=("Segoe UI", 11), bg=self.colors["bg"]).pack(anchor="w", pady=(0,5))
        amt_entry_bt = tk.Entry(pad_frame_bt, width=20, font=("Segoe UI", 12), bd=2, relief="flat")
        amt_entry_bt.pack(fill="x", ipady=5)

        tk.Label(pad_frame_bt, text="Currency:", font=("Segoe UI", 11), bg=self.colors["bg"]).pack(anchor="w", pady=(15,5))
        cur_combo_var_bt = tk.StringVar()
        cur_combo_bt = ttk.Combobox(pad_frame_bt, textvariable=cur_combo_var_bt, values=["USD ($)", "Lira (LBP)"], state="readonly", font=("Segoe UI", 11))
        cur_combo_bt.current(0)
        cur_combo_bt.pack(fill="x", ipady=4)

        tk.Label(pad_frame_bt, text="Direction:", font=("Segoe UI", 11), bg=self.colors["bg"]).pack(anchor="w", pady=(15,5))
        dir_combo_var_bt = tk.StringVar()
        dir_combo_bt = ttk.Combobox(pad_frame_bt, textvariable=dir_combo_var_bt, values=["Cash -> Card", "Card -> Cash"], state="readonly", font=("Segoe UI", 11))
        dir_combo_bt.current(0)
        dir_combo_bt.pack(fill="x", ipady=4)

        exchange_btn_bt = tk.Button(bank_transfer_frame, text="CONFIRM TRANSFER", command=lambda: process_transaction("transfer"), bg=self.colors["accent"], fg="white", font=("Segoe UI", 12, "bold"), relief="flat", cursor="hand2")
        exchange_btn_bt.pack(side=tk.BOTTOM, fill="x", pady=20, padx=20, ipady=10)

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
                    result_text_ce.set(f"Will Receive: {res:,.2f}")

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
        dir_combo_ce.bind("<<ComboboxSelected>>", update_preview)

    def toggle_category_state(self, event=None):
        current_type = self.type_combo.get()
        current_store = self.store_combo.get()

        if current_type == "Income":
            self.cat_combo.set("Cash Flow")
            self.cat_combo.config(state="disabled")
        else:
            if current_store in self.system_accounts:

                if current_store == "Main Vault":
                    self.cat_combo.config(state="readonly")
                    self.cat_combo['values'] = self.main_category_list
                    self.cat_combo.current(0)
                
                else:
                    self.cat_combo.config(state="normal")
                    self.cat_combo['values'] = []
                    self.cat_combo.delete(0, "end")

            else:
                self.cat_combo.config(state="readonly")
                self.cat_combo['values'] = self.category_list
                self.cat_combo.current(0)

    def reset_filters(self):
        self.filter_cat.current(0)
        self.filter_type.current(0)
        self.date_from.delete(0, tk.END)
        self.date_to.delete(0, tk.END)
        self.filter_curr.current(0)
        self.filter_paym.current(0)
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

            if t_type == "Income":
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

        self.tree.tag_configure("oddrow", background="#f0f0f0")
        self.tree.tag_configure("evenrow", background="white")

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

            if f_cat != "All":

                if f_cat == "Exchange In/Out":
                    allowed_categories = ["Exchange In", "Exchange Out"]

                elif store_name in self.system_accounts:
                    allowed_categories = [f_cat, f"from {f_cat}"]

                else:
                    allowed_categories = [f_cat]

                if categ not in allowed_categories:
                    continue

            

            self.current_data.append(row)

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
        self.status_label.config(text=report, font=("Consolas", 12, "bold"), justify=tk.LEFT)

        
    def update_filter_dropdown(self, event=None):
        current_store = self.store_combo.get()
        f_type = self.filter_type.get()

        new_values = ["All"]

        if current_store in self.system_accounts:
            if f_type == "Income":
                self.filter_cat.config(state="readonly")
                all_branches = self.db.get_store_names()
                real_branches = [s for s in all_branches if s not in self.system_accounts]
                new_values += real_branches

            elif f_type == "Expense":
                if current_store == "Main Vault":
                    self.filter_cat.config(state="readonly")
                    new_values += self.main_category_list
                else:
                    self.filter_cat.config(state="normal")
                    self.filter_cat.delete(0, "end")

            else :
                self.filter_cat.config(state="readonly")
                all_branches = self.db.get_store_names()
                real_branches = [s for s in all_branches if s not in self.system_accounts]
                if current_store == "Main Vault":
                    new_values += self.main_category_list + real_branches
                else:
                    new_values += real_branches
        

        else :
            self.filter_cat.config(state="readonly")
            if f_type == "Income":
                new_values += ["Cash Flow"]
            elif f_type == "Expense":
                new_values += self.category_list
            else:
                new_values += self.category_list + ["Cash Flow"]

        self.filter_cat['values'] = new_values
        self.filter_cat.current(0)

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

        style.theme_use('clam')

        style.configure("Treeview", 
                        background="white",
                        foreground="black",
                        rowheight=30, 
                        fieldbackground="white",
                        font=("Segoe UI", 10))
        
        
        style.configure("Treeview.Heading", 
                        font=("Segoe UI", 11, "bold"),
                        background="#dfe6e9",
                        foreground="#2d3436")
        
        
        style.configure("TLabelframe", background=self.colors["bg"])
        style.configure("TLabelframe", font=("Segoe UI", 10, "bold"), background=self.colors["bg"], foreground="#2c3e50")


if __name__ == "__main__":
    root = tk.Tk()
    app = StoreApp(root)
    root.mainloop()
    