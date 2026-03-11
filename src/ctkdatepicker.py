"""Provide a CustomTkinter widget for selecting dates."""

# This is a modified version of CTkDatePicker by Max:
# https://github.com/maxverwiebe/CTkDatePicker
from datetime import datetime, date
import calendar

import tkinter as tk
import customtkinter as ctk


class CTkDatePicker(ctk.CTkFrame):
    """Create and update a calendar widget with CustomTkinter style."""

    def __init__(self, master=None, start_date=None, **kwargs):
        """
        Initialize the CTkDatePicker instance.

        Parameters:
        - master: The parent widget.
        - **kwargs: Additional keyword arguments passed to the CTkFrame constructor.

        Initializes the date entry, calendar button, popup,
        and other related components.
        """
        super().__init__(master, **kwargs)

        self.popup = None
        self.selected_date = None
        self.date_format = "%m/%d/%Y"
        self.allow_manual_input = True
        self.allow_change_month = True
        self.add_months = 0
        self.subtract_months = 0
        self.date_selected_callback = None
        self.date_typed_callback = None

        # Set calendar's date to the set date
        if start_date:
            self.current_year = start_date.year
            self.current_month = start_date.month
            self.current_day = start_date.day
        else:
            # Else, set the calendar to today.
            self.current_year = datetime.now().year
            self.current_month = datetime.now().month
            self.current_day = datetime.now().day

        self.date_entry = ctk.CTkEntry(self, width=90)
        self.date_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        # Set entry text value to initial date
        self.selected_date = datetime(
            self.current_year, self.current_month, self.current_day
        )
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, self.selected_date.strftime(self.date_format))

        self.calendar_button = ctk.CTkButton(
            self, text="▼", width=20, command=self.open_calendar
        )
        self.calendar_button.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # close popup on focus loss
        # self.bind("<<FocusOut>>", self.close_popup)

    def set_callback(self, callback):
        """Set a callback when a user selects a date from the popup calendar."""
        self.date_selected_callback = callback

        # Bind the <KeyRelease> event to the entry widget
        self.date_entry.bind("<KeyRelease>", callback)

    def set_date(self, date_in):
        """Set internal and displayed date to the input date."""
        self.current_year = date_in.year
        self.current_month = date_in.month
        self.current_day = date_in.day
        # Set entry text value to initial date
        self.selected_date = datetime(
            self.current_year, self.current_month, self.current_day
        )
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, self.selected_date.strftime(self.date_format))

    def set_date_format(self, date_format):
        """
        Set the date format to be used in the date entry.

        Parameters:
        - date_format (str): The desired date format string, e.g., "%m/%d/%Y".

        Sets the format in which the selected date will be displayed.
        """
        self.date_format = date_format

    def set_localization(self, localization):
        """
        Set the localization for month and day names.

        Parameters:
        - localization (str): The desired localization string, e.g., "en_EN".

        Sets the language that month and day names will be displayed.
        """
        import locale

        locale.setlocale(locale.LC_ALL, localization)
        locale.setlocale(locale.LC_NUMERIC, "C")

    # def close_popup(self, event):
    #    if self.popup is not None:
    #        self.popup.destroy()
    #        self.popup = None

    def open_calendar(self):
        """
        Open the calendar popup for date selection.

        Creates and displays a calendar widget allowing the user to select a date.
        The calendar appears just below the date entry field.
        """
        # If-else block acts as a toggle for opening/closing the popup
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None

        self.popup = ctk.CTkToplevel(self)
        self.popup.title("Select Date")
        self.popup.geometry(
            "+%d+%d" % (self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        )
        self.popup.resizable(False, False)

        self.popup.after(500, lambda: self.popup.focus())

        self.build_calendar()

    def build_calendar(self):
        """
        Build and display the calendar in the popup.

        Constructs the calendar UI for the currently selected month and year.
        Includes navigation buttons for previous and next months if enabled.
        """
        if hasattr(self, "calendar_frame"):
            self.calendar_frame.destroy()

        self.calendar_frame = ctk.CTkFrame(self.popup)
        self.calendar_frame.grid(row=0, column=0)

        # Add months
        if self.add_months < 0:
            raise ValueError("add_months cannot be negative")
        for i in range(self.add_months):
            if self.current_month == 12:
                self.current_month = 1
                self.current_year += 1
            else:
                self.current_month += 1

        # Subtract months
        if self.subtract_months < 0:
            raise ValueError("subtract_months cannot be negative")
        for i in range(self.subtract_months):
            if self.current_month == 1:
                self.current_month = 12
                self.current_year -= 1
            else:
                self.current_month -= 1

        # Month and Year Selector
        month_label = ctk.CTkLabel(
            self.calendar_frame,
            text=f"{calendar.month_name[self.current_month].capitalize()},"
            f" {self.current_year}",
        )
        month_label.grid(row=0, column=1, columnspan=5)

        if self.allow_change_month:
            prev_month_button = ctk.CTkButton(
                self.calendar_frame, text="<", width=5, command=self.prev_month
            )
            prev_month_button.grid(row=0, column=0)

            next_month_button = ctk.CTkButton(
                self.calendar_frame, text=">", width=5, command=self.next_month
            )
            next_month_button.grid(row=0, column=6)

        # Days of the week header
        days = [calendar.day_name[i][:3].capitalize() for i in range(7)]
        for i, day in enumerate(days):
            lbl = ctk.CTkLabel(self.calendar_frame, text=day)
            lbl.grid(row=1, column=i)

        # Days in month
        month_days = calendar.monthrange(self.current_year, self.current_month)[1]
        start_day = calendar.monthrange(self.current_year, self.current_month)[0]
        day = 1
        for week in range(2, 8):
            for day_col in range(7):
                if week == 2 and day_col < start_day:
                    lbl = ctk.CTkLabel(self.calendar_frame, text="")
                    lbl.grid(row=week, column=day_col)
                elif day > month_days:
                    lbl = ctk.CTkLabel(self.calendar_frame, text="")
                    lbl.grid(row=week, column=day_col)
                else:
                    if ctk.get_appearance_mode() == "Light":
                        btn = ctk.CTkButton(
                            self.calendar_frame,
                            text=str(day),
                            width=3,
                            command=lambda day=day: self.select_date(day),
                            fg_color="transparent",
                            text_color="black",
                            hover_color="#3b8ed0",
                        )
                    else:
                        btn = ctk.CTkButton(
                            self.calendar_frame,
                            text=str(day),
                            width=3,
                            command=lambda day=day: self.select_date(day),
                            fg_color="transparent",
                        )
                    btn.grid(row=week, column=day_col)
                    day += 1

    def prev_month(self):
        """
        Navigate to the previous month in the calendar.

        Updates the calendar display to show the previous month's days.
        Adjusts the year if necessary.
        """
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.build_calendar()

    def next_month(self):
        """
        Navigate to the next month in the calendar.

        Updates the calendar display to show the next month's days.
        Adjusts the year if necessary.
        """
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.build_calendar()

    def select_date(self, day):
        """
        Select a date from the calendar.

        Parameters:
        - day (int): The day of the month selected by the user.

        Sets the selected date in the date entry field and closes the calendar popup.
        """
        self.selected_date = datetime(self.current_year, self.current_month, day)
        # Temporarily enable the entry to set the date
        self.date_entry.configure(state="normal")
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, self.selected_date.strftime(self.date_format))
        # Restore the disabled state if necessary
        if not self.allow_manual_input:
            self.date_entry.configure(state="disabled")
        self.popup.destroy()
        self.popup = None

        # Trigger a callback
        if self.date_selected_callback:
            self.date_selected_callback()

    def get_date_str(self):
        """
        Get the currently selected date as a string.

        Returns:
        - str: The date string in the format specified by self.date_format.
        """
        return self.date_entry.get()

    def get_date(self):
        """
        Get the currently selected date as a datetime.date.

        Requires m/d/y format.

        Returns:
            True if the date is valid and matches the format, False otherwise.
        """
        try:
            date_out = self.date_entry.get().split("/")
            date_out = date(
                year=int(date_out[2]), month=int(date_out[0]), day=int(date_out[1])
            )
            return date_out
        except ValueError:
            # A ValueError is raised if the string does not match the format
            # or the date itself is invalid (e.g., Feb 31st).
            return None

    def set_allow_manual_input(self, value):
        """
        Enable or disable manual date input.

        Parameters:
        - value (bool): If True, manual input in the date entry is allowed;
        otherwise, it is disabled.

        Allows the user to manually enter a date if set to True; otherwise,
        restricts input to selection via the calendar.
        """
        self.allow_manual_input = value
        if not value:
            self.date_entry.configure(state="disabled")
        else:
            self.date_entry.configure(state="normal")

    def set_allow_change_month(self, value):
        """
        Enable or disable change month.

        Parameters:
        - value (bool): If False, user cannot change month in the calendar.

        Allows the user to change month if set to True; otherwise,
        removes the arrows to change month.
        """
        self.allow_change_month = value

    def set_change_months(self, add_or_sub, value):
        """
        Add or subract number of months when opening the calendar.

        Parameters:
        - add_or_sub (str): Either "add" or "sub".
        - value (int): Number of months.

        Set a number of months to add or subract when opening the calendar.
        """
        if add_or_sub == "add":
            self.add_months = value
        elif add_or_sub == "sub":
            self.subtract_months = value
        else:
            raise ValueError("Invalid value for add_or_sub. Must be 'add' or 'sub'")
