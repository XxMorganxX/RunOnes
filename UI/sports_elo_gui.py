import tkinter as tk


class SportsEloApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SportsElo")
        self.root.geometry("400x300")
        
        # Create the first page
        self.create_first_page()
    
    def create_first_page(self):
        """Create the first page with title and button"""
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Title
        title_label = tk.Label(
            self.root,
            text="SportsElo",
            font=("Arial", 24, "bold"),
            pady=40
        )
        title_label.pack()
        
        # Button
        press_button = tk.Button(
            self.root,
            text="press me!",
            command=self.open_second_window,
            font=("Arial", 14),
            bg="#4CAF50",
            fg="black",
            activebackground="#45a049",
            activeforeground="white",
            padx=20,
            pady=10,
            cursor="hand2",
            highlightthickness=0,
            relief="raised"
        )
        press_button.pack(pady=20)
        # Force button to update its appearance
        press_button.update_idletasks()
    
    def open_second_window(self):
        """Debug print and open second window"""
        print("DEBUG: Button clicked! Opening second window...")
        self.create_second_page()
    
    def create_second_page(self):
        """Create the second page with input boxes and submit button"""
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Frame for inputs
        input_frame = tk.Frame(self.root, pady=20)
        input_frame.pack(expand=True)
        
        # First input box
        tk.Label(
            input_frame,
            text="Input 1:",
            font=("Arial", 12)
        ).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        
        self.input1 = tk.Entry(input_frame, font=("Arial", 12), width=25)
        self.input1.grid(row=0, column=1, padx=10, pady=10)
        
        # Second input box
        tk.Label(
            input_frame,
            text="Input 2:",
            font=("Arial", 12)
        ).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        
        self.input2 = tk.Entry(input_frame, font=("Arial", 12), width=25)
        self.input2.grid(row=1, column=1, padx=10, pady=10)
        
        # Submit button
        submit_button = tk.Button(
            self.root,
            text="Submit",
            command=self.submit_data,
            font=("Arial", 14),
            bg="#2196F3",
            fg="black",
            activebackground="#1976D2",
            activeforeground="white",
            padx=30,
            pady=10,
            cursor="hand2",
            highlightthickness=0,
            relief="raised"
        )
        submit_button.pack(pady=20)
        submit_button.update_idletasks()
        
        # Back button (optional, for navigation)
        back_button = tk.Button(
            self.root,
            text="← Back",
            command=self.create_first_page,
            font=("Arial", 10),
            bg="#757575",
            fg="black",
            activebackground="#616161",
            activeforeground="white",
            padx=15,
            pady=5,
            cursor="hand2",
            highlightthickness=0,
            relief="raised"
        )
        back_button.pack()
        back_button.update_idletasks()
    
    def submit_data(self):
        """Handle submit button click"""
        value1 = self.input1.get()
        value2 = self.input2.get()
        
        print("DEBUG: Submit clicked!")
        print(f"  Input 1: {value1}")
        print(f"  Input 2: {value2}")
        
        # Optionally clear the inputs after submission
        self.input1.delete(0, tk.END)
        self.input2.delete(0, tk.END)
        
        # Show confirmation message
        confirmation = tk.Label(
            self.root,
            text="✓ Data submitted successfully!",
            font=("Arial", 10),
            fg="green"
        )
        confirmation.pack()
        
        # Remove confirmation message after 2 seconds
        self.root.after(2000, confirmation.destroy)


def main():
    root = tk.Tk()
    app = SportsEloApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

