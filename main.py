import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv

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
        self.c.execute("SELECT count(*) FROM stores")
        count = self.c.fetchone()[0]

        if count == 0 :
            default_branches = ["LeMall Dbayye", "City Center", "City Mall", "Koura Branch"]
            for x in default_branches:
                self.c.execute("INSERT INTO stores (name) VALUES (?)", (x,))
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
        
#This class will be used for the user interface (GUI)
class StoreApp:
    #This will create the root of the window, link the db class and setup the page
    def __init__(self, root):
        self.root = root
        self.root.title("Management System")
        self.root.geometry("900x600")

        self.db = DatabaseManager()

        self.setup_styles()

        self.category_list = [
            "Credit Card Commission",
            "Salaries",
            "Rent",
            "Yearly Fees",
            "Electricity Chiller",
            "Phone",
            "Various",  
        ]

        self.setup_header()
        self.setup_inputs()
        self.setup_table()

        self.view_records()

    def setup_header(self):
        #the frame for the header
        header_frame = tk.Frame(self.root, pady = 10, bg = "#f0f0f0")
        header_frame.pack(fill="x")

        #Now the Title on top of the page
        tk.Label(header_frame, text="Select Branch", bg="#f0f0f0", font=("Arial", 12)).pack(side=tk.LEFT, padx=10)

        #Now under it we want to branch dropdown menu
        self.store_var = tk.StringVar()
        self.store_combo = ttk.Combobox(header_frame, textvariable=self.store_var, state="readonly")

        self.store_combo['values'] = self.db.get_store_names()
        self.store_combo.current(0)
        self.store_combo.pack(side=tk.LEFT)

        self.store_combo.bind("<<ComboboxSelected>>", lambda e: self.view_records())

    def setup_inputs(self):
        input_frame = tk.LabelFrame(self.root, text="New Transaction", padx= 10, pady= 10)
        input_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(input_frame, text="Type").grid(row=0, column=0)
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(input_frame, textvariable=self.type_var, values=["Income","Expense"], state="readonly")
        self.type_combo.current(0)
        self.type_combo.grid(row=1, column=0, padx=5, pady=5)
        

        tk.Label(input_frame, text="Category").grid(row=0, column=1)
        self.cat_var = tk.StringVar()
        self.cat_combo = ttk.Combobox(input_frame, textvariable=self.cat_var, values=self.category_list, state = "readonly")
        self.cat_combo.current(0)
        self.cat_combo.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(input_frame, text="Currency").grid(row=0, column=2)
        self.currency_var = tk.StringVar()
        self.cur_combo = ttk.Combobox(input_frame, textvariable=self.currency_var, values=["USD ($)", "Lira (LBP)"], state="readonly")
        self.cur_combo.current(0)
        self.cur_combo.grid(row=1, column=2, padx=5, pady=5)

        tk.Label(input_frame, text="Payment Method").grid(row=2, column=0)
        self.paym_var = tk.StringVar()
        self.paym_combo = ttk.Combobox(input_frame, textvariable=self.paym_var, values=["Cash", "Card"], state="readonly")
        self.paym_combo.current(0)
        self.paym_combo.grid(row=3, column=0, padx=5, pady=5)

        tk.Label(input_frame, text="Amount ($)").grid(row=2, column=1)
        self.amount_entry = tk.Entry(input_frame)
        self.amount_entry.grid(row=3, column=1, padx=5, pady=5)

        tk.Button(input_frame, text="+ Add Transaction", bg="green", fg="white", command=self.add_records).grid(row=3, column=2, padx=10, pady=5)

    def setup_table(self):
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        filter_frame = tk.Frame(tree_frame)
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="Filter Type:").pack(side=tk.LEFT)
        self.filter_type_var = tk.StringVar()
        self.filter_type = ttk.Combobox(filter_frame, textvariable="self.filter_type_var", values=["All", "Income", "Expense"], state="readonly", width=10)
        self.filter_type.current(0)
        self.filter_type.pack(side=tk.LEFT, padx=5)

        tk.Label(filter_frame, text="Filter Category:").pack(side=tk.LEFT)
        full_cat_list = ["All"] + self.category_list
        self.filter_cat_var = tk.StringVar()
        self.filter_cat = ttk.Combobox(filter_frame, textvariable="self.filter_cat_var", values= full_cat_list, state="readonly", width=15)
        self.filter_cat.current(0)
        self.filter_cat.pack(side=tk.LEFT, padx=5)

        self.filter_type.bind("<<ComboboxSelected>>", lambda e: self.view_records())
        self.filter_cat.bind("<<ComboboxSelected>>", lambda e: self.view_records())

        tk.Button(filter_frame, text="Reset Filter", command = self.reset_filters).pack(side=tk.LEFT, padx=10)

        cols = ("ID", "date", "Type", "Category", "Amount", "Currency", "Payment Method")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings")

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        self.tree.pack(fill="both", expand=True)

        bottom_frame = tk.Frame(tree_frame)
        bottom_frame.pack(fill="x", pady=10)

        delete_btn = tk.Button(bottom_frame, text="Delete Selected Row", bg="red", fg="white", command=self.delete_record)
        delete_btn.pack(side=tk.LEFT, padx=5)

        export_btn = tk.Button(bottom_frame, text="Export to Excel", bg="#006400", fg="white", command=self.export_to_excel)
        export_btn.pack(side=tk.LEFT, padx=5)

        #He placeholder ma bt bayyin b bayyin mahala l hateto b show records and __init__ he bas just to be safe
        self.status_label = tk.Label(bottom_frame, text="Balance: $0.00", font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.RIGHT)

    def reset_filters(self):
        self.filter_cat.current(0)
        self.filter_type.current(0)
        self.view_records()

    def delete_record(self):
        selected_item = self.tree.selection()

        if not selected_item:
            messagebox.showwarning("Warning", "Please select a row to delete")
            return
        
        confirm = messagebox.askyesno("Confirm", "Are you sure you want to delete this entry ?")
        if confirm:
            row_data = self.tree.item(selected_item)
            record_id = row_data['values'][0]

            self.db.delete_transaction(record_id)

            self.view_records()
            messagebox.showinfo("Succes", "Record Deleted")

    def add_records(self):
        store = self.store_combo.get()
        t_type = self.type_combo.get()
        cat = self.cat_combo.get()
        amt = self.amount_entry.get()
        cur = self.cur_combo.get()
        paym = self.paym_combo.get()

        if not cat or not amt:
            messagebox.showerror("Error", "Please fill all the fields")
            return
        
        try:
            val = float(amt)

            today = datetime.now().strftime("%d-%m-%Y")

            self.db.add_transactions(store, today, t_type, cat, val, cur, paym)

            messagebox.showinfo("Succes", "Transaction Saved!")

            self.view_records()

            self.cat_combo.set('')
            self.amount_entry.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number")

    def view_records(self):
        store_name = self.store_combo.get()

        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.get_transactions(store_name)

        f_type = self.filter_type.get()
        f_cat = self.filter_cat.get()

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

            if f_type != "All" and t_type != f_type:
                continue

            if f_cat != "All" and categ != f_cat:
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
                        rowheight=25, 
                        fieldbackground="white",
                        font=("Arial", 10))
        
        
        style.configure("Treeview.Heading", 
                        font=("Arial", 11, "bold"),
                        background="#dddddd")
        
        
        style.configure("TCombobox", padding=5)
        style.configure("TEntry", padding=5)


if __name__ == "__main__":
    root = tk.Tk()
    app = StoreApp(root)
    root.mainloop()

