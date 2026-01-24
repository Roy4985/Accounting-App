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
                       date TEXT,
                       type TEXT,
                       category TEXT,
                       amount REAL,
                       currency TEXT,
                       payment_method TEXT
                       )
        """)


        self.seed_data()

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

        
    def add_transactions(self, store_name, t_date, t_type, category, amount, currency, p_method):
        self.c.execute("SELECT id FROM stores WHERE name = ?", (store_name,))
        result = self.c.fetchone()

        if result:
            store_id = result[0]

            self.c.execute("INSERT INTO transactions (store_id, date, type, category, amount, currency, payment_method) VALUES (?,?,?,?,?,?,?)", (store_id, t_date, t_type, category, amount, currency, p_method))
            self.conn.commit()
        else:
            print("Error, Store not found")

    def get_transactions(self, store_name):
        self.c.execute("""
            SELECT t.id, t.date, t.type, t.category, t.amount, t.currency, t.payment_method FROM transactions t
            JOIN stores s ON t.store_id = s.id
            WHERE s.name = ?
            ORDER BY t.date DESC
        """, (store_name,))

        return self.c.fetchall()
    
    def delete_transaction(self, trans_id):
        self.c.execute("DELETE FROM transactions WHERE id = ?", (trans_id,))
        self.conn.commit()

    def delete_smart_chain(self, main_id, store_name, t_date, amount, p_method, currency):
        self.delete_transaction(main_id)

        self.c.execute("SELECT id FROM stores WHERE name = ?", (store_name,))
        src_res = self.c.fetchone()
        if not src_res:
            print("Error : Source store not found for deletion")
            return
        src_id = src_res[0]

        val = float(amount)
        amt_main = round(val * 0.15,2)
        amt_tva = round(val * 0.07,2)

        def delete_single_match(s_id, date, cat, amt):
            sql = """
                SELECT id FROM transactions 
                WHERE store_id=? AND date=? AND category=? AND amount=? AND currency=? AND payment_method=? 
                LIMIT 1
            """
            self.c.execute(sql, (s_id, date, cat, amt, currency, p_method))
            
            match = self.c.fetchone()
            if match:
                self.c.execute("DELETE FROM transactions WHERE id=?", (match[0],))

        desc_main_out = "Main (15%)"
        desc_main_in  = f"from {store_name}"
        
        desc_tva_out  = "TVA (7%)"
        desc_tva_in   = f"from {store_name}"
        
        delete_single_match(src_id, t_date, desc_main_out, amt_main)
        
        
        self.c.execute("SELECT id FROM stores WHERE name='Main Vault'")
        res_vault = self.c.fetchone()
        if res_vault:
            delete_single_match(res_vault[0], t_date, desc_main_in, amt_main)

        delete_single_match(src_id, t_date, desc_tva_out, amt_tva)
        
        self.c.execute("SELECT id FROM stores WHERE name='TVA Account'")
        res_tva = self.c.fetchone()
        if res_tva:
            delete_single_match(res_tva[0], t_date, desc_tva_in, amt_tva)

        if p_method == "Card":
            amt_comm = round(val * 0.03, 2)
            desc_comm_out = "Card Commission (3%)"
            desc_comm_in  = f"from {store_name}"
            
            delete_single_match(src_id, t_date, desc_comm_out, amt_comm)
            
            self.c.execute("SELECT id FROM stores WHERE name='Bank Commission'")
            res_bank = self.c.fetchone()
            if res_bank:
                delete_single_match(res_bank[0], t_date, desc_comm_in, amt_comm)

        self.conn.commit()
        print("Cascading delete complete (Single items only).")

    def delete_cost_of_goods_chain(self, expense_id, store_name, t_date, amount, currency):
        self.delete_transaction(expense_id)

        val = float(amount)
        amt_freight = round(val * 0.33, 2)
        desc_in = f"from {store_name}"

        def delete_single_match(s_name, trans_type, cat, amt):
            self.c.execute("SELECT id FROM stores WHERE name=?", (s_name,))
            res_store = self.c.fetchone()
            if not res_store: return
            s_id = res_store[0]

            sql = """SELECT id FROM transactions 
                     WHERE store_id=? AND date=? AND type=? AND category=? AND amount=? AND currency=? 
                     LIMIT 1"""
            self.c.execute(sql, (s_id, t_date, trans_type, cat, amt, currency))
            match = self.c.fetchone()
            
            if match:
                self.c.execute("DELETE FROM transactions WHERE id=?", (match[0],))
        
        delete_single_match("Cost of goods", "Income", desc_in, val)

        delete_single_match(store_name, "Expense", "Freight", amt_freight)

        delete_single_match("Freight", "Income", desc_in, amt_freight)
        
        self.conn.commit()
        print("Cost of Goods chain deleted.")

        
#This class will be used for the user interface (GUI)
class StoreApp:
    #This will create the root of the window, link the db class and setup the page
    def __init__(self, root):
        self.root = root
        self.root.title("Management System")
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

        self.category_list = [
            "Salaries",
            "Rent",
            "Yearly Fees",
            "Electricity Chiller",
            "Phone",
            "Various",
            "Cost of goods",  
        ]


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
        title_label = tk.Label(header_frame, text="Select Branch", bg=self.colors["header"], font=("Sego UI", 18, "bold"), fg="white")
        title_label.pack(side=tk.LEFT, padx=20, pady=10)

        all_stores = self.db.get_store_names()

        #Now under it we want to branch dropdown menu
        self.store_var = tk.StringVar()
        self.store_combo = ttk.Combobox(header_frame, textvariable=self.store_var, values=all_stores, state="readonly")

        self.store_combo.current(0)
        self.store_combo.pack(side=tk.RIGHT, padx=20, pady=10)

        self.store_combo.bind("<<ComboboxSelected>>", lambda e: self.view_records())

    def setup_inputs(self):
        master_frame = tk.Frame(self.root, bg=self.colors["bg"])
        master_frame.pack(fill="x", padx=20, pady=15)

        #Input side 
        input_frame = tk.LabelFrame(master_frame, text="New Transaction")
        input_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0,10))

        tk.Label(input_frame, text="Date", bg=self.colors["bg"]).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.date_entry = DateEntry(input_frame, width=12, background="darkblue", foreground='white', borderwidth=2, date_pattern='y-mm-dd')
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

        add_btn = tk.Button(input_frame, text="+ Add Record", bg=self.colors["success"], fg="white", font=("Sego UI", 10, "bold") ,command=self.add_records)
        add_btn.grid(row=2, column=0, columnspan=6, stick="ew", padx=10, pady=10)

        #filter side
        filter_frame = ttk.LabelFrame(master_frame, text="Filters")
        filter_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=(10,0))

        tk.Label(filter_frame, text="Filter Type:", bg=self.colors["bg"]).grid(row=0, column=0, padx=5, pady=10)
        self.filter_type_var = tk.StringVar()
        self.filter_type = ttk.Combobox(filter_frame, textvariable="self.filter_type_var", values=["All", "Income", "Expense"], state="readonly", width=10)
        self.filter_type.current(0)
        self.filter_type.grid(row=0, column=1, padx=5)

        tk.Label(filter_frame, text="Filter Category:", bg=self.colors["bg"]).grid(row=0, column=2, padx=5, pady=10)
        full_cat_list = ["All", "Cash Flow"] + self.category_list
        self.filter_cat_var = tk.StringVar()
        self.filter_cat = ttk.Combobox(filter_frame, textvariable="self.filter_cat_var", values= full_cat_list, state="readonly", width=15)
        self.filter_cat.current(0)
        self.filter_cat.grid(row=0, column=3, padx=5)

        tk.Label(filter_frame, text="From:", bg=self.colors["bg"]).grid(row=1, column=0, padx=5, pady=5)
        self.date_from = DateEntry(filter_frame, width=12, background="darkblue", foreground='white', borderwidth=2, date_pattern='y-mm-dd')
        self.date_from.delete(0, "end")
        self.date_from.grid(row=1, column=1, padx=5)

        tk.Label(filter_frame, text="To:", bg=self.colors["bg"]).grid(row=1, column=2, padx=5, pady=5)
        self.date_to = DateEntry(filter_frame, width=12, background="darkblue", foreground='white', borderwidth=2, date_pattern='y-mm-dd')
        self.date_to.delete(0, "end")
        self.date_to.grid(row=1, column=3, padx=5)

        btn_frame = tk.Frame(filter_frame, )
        btn_frame.grid(row=2, column=0, columnspan=4, pady=5)

        tk.Button(btn_frame, text="Apply Filter", bg="#2c3e50", fg="white", command=self.view_records).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset", command = self.reset_filters).pack(side=tk.LEFT, padx=5)

        self.filter_type.bind("<<ComboboxSelected>>", lambda e: self.view_records())
        self.filter_cat.bind("<<ComboboxSelected>>", lambda e: self.view_records())


    def setup_table(self):
        main_content = tk.Frame(self.root, bg=self.colors["bg"])
        main_content.pack(fill="both", expand=True, padx=20, pady=(0,20))


        tree_frame = tk.Frame(main_content)
        tree_frame.pack(fill="both", expand=True)

        cols = ("ID", "Date", "Type", "Category", "Amount", "Currency", "Payment Method")

        visible_cols = ("Date", "Type", "Category", "Amount", "Currency", "Payment Method")

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", displaycolumns=visible_cols)

        self.tree.column("Date", width=100, anchor=tk.CENTER)
        self.tree.column("Type", width=80, anchor=tk.CENTER)
        self.tree.column("Category", width=150, anchor=tk.W)
        self.tree.column("Amount", width=100, anchor=tk.E)  
        self.tree.column("Currency", width=80, anchor=tk.CENTER)
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

        delete_btn = tk.Button(bottom_frame, text="Delete Selected", bg=self.colors["danger"], fg="white", command=self.delete_record)
        delete_btn.pack(side=tk.LEFT, padx=5)

        export_btn = tk.Button(bottom_frame, text="Export to Excel", bg=self.colors["accent"], fg="white", command=self.export_to_excel)
        export_btn.pack(side=tk.LEFT, padx=5)

        #He placeholder ma bt bayyin b bayyin mahala l hateto b show records and __init__ he bas just to be safe
        self.status_label = tk.Label(bottom_frame, text="Loading...", font=("Sego UI", 10, "bold"), bg=self.colors["bg"], justify=tk.RIGHT)
        self.status_label.pack(side=tk.RIGHT)

    def toggle_category_state(self, event=None):
        current_type = self.type_combo.get()

        if current_type == "Income":
            self.cat_combo.set("Cash Flow")
            self.cat_combo.config(state="disabled")
        else:
            self.cat_combo.config(state="readonly")
            self.cat_combo['values'] = self.category_list

            if self.category_list:
                self.cat_combo.current(0)

    def reset_filters(self):
        self.filter_cat.current(0)
        self.filter_type.current(0)
        self.date_from.delete(0, tk.END)
        self.date_to.delete(0, tk.END)
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
            record_date = row_data[1]
            record_type = row_data[2]
            record_cat = row_data[3]
            record_store = self.store_combo.get()
            record_amount = row_data[4]
            record_curr = row_data[5]
            record_paym = row_data[6]

            if record_type == "Income":
                self.db.delete_smart_chain(record_id, record_store, record_date, record_amount, record_paym, record_curr)
            elif record_type == "Expense" and record_cat == "Cost of goods":
                self.db.delete_cost_of_goods_chain(record_id, record_store, record_date, record_amount, record_curr) 
            else:
                self.db.delete_transaction(record_id)

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

        if not date_val.strip():
            date_val = datetime.now().strftime("%Y-%m-%d")

        if not cat or not amt:
            messagebox.showerror("Error", "Please fill all the fields")
            return
        
        try:
            val = float(amt)

            today = date_val

            self.db.add_transactions(store, today, t_type, cat, val, cur, paym)

            if cat == "Cost of goods" and t_type == "Expense":
                self.db.add_transactions("Cost of goods", today, "Income", f"from {store}", val, cur, paym)
                amt_freight = round(val * 0.33, 2)
                self.db.add_transactions(store, today, "Expense", "Freight", amt_freight, cur, paym)
                self.db.add_transactions("Freight", today, "Income", f"from {store}", amt_freight, cur, paym)

            if t_type == "Income":
                amount_main = round(val * 0.15, 2)
                self.db.add_transactions(store, today, "Expense", "Main (15%)", amount_main, cur, paym)
                self.db.add_transactions("Main Vault", today, "Income", f"from {store}", amount_main, cur, paym)

                amount_tva = round(val * 0.07, 2)
                self.db.add_transactions(store, today, "Expense", "TVA (7%)", amount_tva, cur, paym)
                self.db.add_transactions("TVA Account", today, "Income", f"from {store}", amount_tva, cur, paym)

                if paym == "Card":
                    amount_card = round(val * 0.03, 2)
                    self.db.add_transactions(store, today, "Expense", "Card Commission (3%)", amount_card, cur, paym)
                    self.db.add_transactions("Bank Commission", today, "Income", f"from {store}", amount_card, cur, paym)

            messagebox.showinfo("Succes", "Transaction Saved!")

            self.amount_entry.delete(0, tk.END)
            self.date_entry.set_date(datetime.now())

            self.type_combo.current(0)
            self.toggle_category_state()

            self.view_records()
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number")

    def view_records(self):
        store_name = self.store_combo.get()

        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.get_transactions(store_name)

        f_type = self.filter_type.get()
        f_cat = self.filter_cat.get()

        start_date = self.date_from.get()
        end_date = self.date_to.get()

        total_usd_cash = 0
        total_usd_card = 0
        total_lbp_cash = 0
        total_lbp_card = 0

        self.tree.tag_configure("oddrow", background="#f0f0f0")
        self.tree.tag_configure("evenrow", background="white")

        count = 0


        for row in rows:
            t_type = row[2]
            categ = row[3]
            date = row[1]

            if f_type != "All" and t_type != f_type:
                continue

            if f_cat != "All" and categ != f_cat:
                continue

            if start_date and date < start_date:
                continue

            if end_date and date > end_date:
                continue

            if count % 2 == 0:
                self.tree.insert("", "end", values=row, tags=("evenrow",))
            else:
                self.tree.insert("", "end", values=row, tags=("oddrow",))
            
            count += 1

            
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


        report = f"USD Cash: ${total_usd_cash:,.2f} | USD Card ${total_usd_card:,.2f}\n LBP Cash: {total_lbp_cash:,.0f} L.L | LBP Card: {total_lbp_card:,.0f} L.L"
        self.status_label.config(text=report, font=("Arial", 10, "bold"), justify=tk.LEFT)
        
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
        rows = self.db.get_transactions(store_name)

        try:
            with open(filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                headers = ["ID", "Date", "Type", "Category", "Amount", "Currency", "Method"]
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
                        font=("Sego UI", 10))
        
        
        style.configure("Treeview.Heading", 
                        font=("Sego UI", 11, "bold"),
                        background="#dfe6e9",
                        foreground="#2d3436")
        
        
        style.configure("TLabelframe", background=self.colors["bg"])
        style.configure("TLabelframe", font=("Sego UI", 10, "bold"), background=self.colors["bg"], foreground="#2c3e50")


if __name__ == "__main__":
    root = tk.Tk()
    app = StoreApp(root)
    root.mainloop()
    

