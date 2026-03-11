"""Main module for Horizon's functionality."""

import math
from functools import partial
import shutil
import datetime
from datetime import date
from datetime import timedelta
import pathlib
import logging
import os
import json
import time
import tkinter
import tkinter.messagebox
from tkinter import ttk

from dateutil.relativedelta import relativedelta
import humanize
import numpy as np
import matplotlib
import matplotlib.dates
import matplotlib.units
import matplotlib.pyplot
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import customtkinter

from ctkdatepicker import CTkDatePicker

# Keycodes for delete on various platforms
keycodes = {
    "delete": [8, 22, 855638143],
    "shift": [50, 943782142],
    "$": [13, 356515876],
    ".": [60, 788529198],
}

NUM_LOGS = 5
NUM_BACKUPS = 5
# Skip plotting jobs that ended OLD_JOB_THRESHOLD days before today.
OLD_JOB_THRESHOLD = 15

# Used to handle updating data from older versions of Horizon.
CURRENT_VERSION = 24

# Use a graphical backend more compatible with OSX devices
matplotlib.use("TkAgg")

# Set the matplotlib date formatter to use a concise built-in version
converter = matplotlib.dates.ConciseDateConverter()
matplotlib.units.registry[np.datetime64] = converter
matplotlib.units.registry[datetime.date] = converter
matplotlib.units.registry[datetime.datetime] = converter

# Check for and create basic directories
os.makedirs(pathlib.Path("data"), exist_ok=True)
os.makedirs(pathlib.Path("data/backups"), exist_ok=True)
os.makedirs(pathlib.Path("data/logs"), exist_ok=True)
# Configure the logger
logging.basicConfig(
    filename=pathlib.Path(f"data/logs/{str(int(time.time()))}.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s -" " %(message)s - %(funcName)s - %(lineno)d",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Get a logger instance
logger = logging.getLogger(__name__)


def lerp(start: float, end: float, t: float) -> float:
    """Interpolate between start and end based on the ratio t."""
    return start + (end - start) * t


def str_to_date(date_in: str) -> datetime.date:
    """
    Convert string to date.

    Parameters:
        date_in (string): Formatted as YYYY-MM-DD
    """
    date_in = date_in.split("-")
    return date(int(date_in[0]), int(date_in[1]), int(date_in[2]))


def date_to_str(date_in: datetime.date) -> str:
    """Convert date to string, formatted as YYYY-MM-DD."""
    years = str(date_in.year).rjust(2, "0")
    months = str(date_in.month).rjust(2, "0")
    days = str(date_in.day).rjust(2, "0")
    return f"{years}-{months}-{days}"


def prune_files_in_dir(dir_path: pathlib.Path, max_files_remaining: int) -> None:
    """Remove old backups to conserve space."""
    try:
        backups = sorted(os.listdir(dir_path))
        if len(backups) > max_files_remaining:
            # Remove all but the most recent (max_files_remaining) backups.
            for backup in backups[: len(backups) - max_files_remaining]:
                file_path = dir_path / backup
                try:
                    os.remove(file_path)
                    logger.info(f"  '{file_path}' deleted successfully.")
                except FileNotFoundError:
                    print(f"Error: File '{file_path}' not found.")
                except PermissionError:
                    print(f"Error: Permission denied to delete '{file_path}'.")
                except OSError as e:
                    print(f"Error deleting file '{file_path}': {e}")
    except FileNotFoundError:
        print(f"Error: Directory '{dir_path}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


class ClientProfileDatabase:
    """Handle client profiles."""

    def __init__(self, jobs: list) -> None:
        """Initialize client database from jobs."""
        # Sets automatically omit duplicate client info.
        self.client_database = set()
        for job in jobs:
            self.add_client_to_database((job["name"], job["phone"]))
        logger.info(
            f"Initialized client database with {len(self.client_database)}" f" clients"
        )

    def add_client_to_database(self, client: tuple) -> None:
        """
        Add a client to database.

        Parameters:
        client (tuple): Formatted as (name: str, phone_number: str)
            Phone numbers should follow the format: +1 (123) 456-7890
        """
        #
        self.client_database.add(client)
        logger.info(
            f"  Added client {client} to database; {len(self.client_database)}"
            f" total clients"
        )

    def get_matching_clients(self, name: str, phone: str) -> list:
        """Get a list of clients with a matching name and phone number."""
        autocomplete_clients = []
        phone_len = len(phone)
        name_len = len(name)
        # A client in the database is deemed a match if the start of client's
        # name/phone match the entire input name/phone.
        # In other words, if a client matches the supplied input (so far),
        # they are a match.
        # Examples:
        # client database: ('hello', '123')
        # input of ('hello', '') -> client matched
        # input of ('h', '') -> client matched
        # input of ('', '123') -> client matched
        # input of ('', '') -> client matched
        # input of ('ello', '') -> no matches
        # input of ('', '3') -> no matches
        # input of ('hello', '4') -> no matches
        for client in self.client_database:
            if phone == client[1][0:phone_len]:
                # Matching is case-insensitive
                if name_len == 0 or name.lower() in client[0].lower():
                    autocomplete_clients.append(client)
                    # Stop searching if there are more than 10 results
                    # if len(autocomplete_clients) == 10:
                    #    break
        logger.info(
            f"Found {len(autocomplete_clients)} autocomplete clients matching"
            f" ({name}, {phone})"
        )
        return autocomplete_clients


class SuggestionsFrame(customtkinter.CTkFrame):
    """
    Handle the popup when displaying suggested clients/jobs.

    This frame is used to handle displaying both suggested clients and jobs;
    the frame will decide which to display based on supplied data.
    Only one instance of this class should exist at a time.

    Parameters:
        master: the calling/root window/widget
        button_callback_func: Called when the user clicks a button.
        button_data: a list of clients or jobs.
    """

    def __init__(self, master, button_callback_func, button_data: list, **kwargs):
        """Initialize all widgets."""
        super().__init__(master, **kwargs)
        self.configure(border_width=5)
        # Maximum number of clients that can be displayed at once

        if isinstance(button_data[0], tuple):
            logger.info("Suggestion frame: using client profile format")
            max_results = 8
            # Currently, the ordering of displayed clients is arbitrary.
            for client in button_data[0:max_results]:
                # Using partial, we supply 'client' as an argument to the
                # function called when the button is pressed
                client_button = customtkinter.CTkButton(
                    self,
                    text=f"{client[0]}\n{client[1]}",
                    command=partial(button_callback_func, client),
                )
                client_button.pack(padx=15, pady=5)
            # if we have more matches that can be displayed, show the number
            # of remaining matches.
            if len(button_data) > max_results:
                summary = customtkinter.CTkButton(
                    self, text=f"Plus {len(button_data) - max_results} more"
                )
                summary.configure(state="disabled")
                summary.pack(padx=15, pady=10)
        else:
            logger.info("Suggestion frame: using job format")
            max_results = 12
            # The jobs list is ordered and sliced to display the most recent
            # jobs, with the oldest at the top of the frame and newest at the
            # bottom of frame
            if len(button_data) > max_results:
                slicing_index = len(button_data) - max_results
            else:
                slicing_index = 0
            for job in button_data[slicing_index:]:
                job_text = job["type"]
                # Clamp long text values to prevent the button resizing or text
                # being abruptly cut off
                if len(job_text) > 17:
                    job_text = job_text[0:14] + "..."
                job_text = f"${job['work_units']} {job_text}\nDue: {job['end']}"
                client_button = customtkinter.CTkButton(
                    self, text=job_text, command=partial(button_callback_func, job)
                )
                client_button.pack(padx=15, pady=5)
                if job["is_complete"]:
                    # A dark blue/white
                    # button_color = '#478EDC'
                    # A soft blue/white
                    # button_color = '#68A1DF'
                    client_button.configure(fg_color="#68A1DF")
                    client_button.configure(hover_color="#478EDC")
            # if we have more jobs than displayed, show a summary of the
            # remaining jobs
            if len(button_data) > max_results:
                summary = customtkinter.CTkButton(
                    self, text=f"Plus {len(button_data) - max_results} more"
                )
                summary.configure(state="disabled")
                summary.pack(padx=15, pady=10)


class FinanceWindow(customtkinter.CTkToplevel):
    """
    Handle the popup window when viewing finances.

    Only one instance of this class should exist at a time.

    Parameters:
        jobs: a sorted list of valid jobs
        options: only options used are 'color_1' to 'color_5'
    """

    def __init__(self, jobs: list, options: dict, *args, **kwargs):
        """Initialize all widgets."""
        super().__init__(*args, **kwargs)
        self.jobs = jobs
        self.options = options
        self.canvas = None
        self.fig = None
        self.geometry("400x330")
        self.title("Finances")

        self.view_button = customtkinter.CTkSegmentedButton(
            self,
            values=["Daily", "Monthly", "Yearly", "Summary"],
            command=self.change_view_button,
        )
        self.view_button.set("Yearly")
        self.view_button.pack(side="top", padx=20, pady=20)
        # Placeholder for the text summary label
        self.summary_label = customtkinter.CTkLabel(self, text="Summary")

        # Display the yearly finance view by default
        self.display_finances_yearly()

    def change_view_button(self, view):
        """Switch view based on user selection."""
        logger.info(f"Displaying {view} finances data")
        if view == "Daily":
            self.summary_label.pack_forget()
            self.display_finances_continuous()
        elif view == "Monthly":
            self.summary_label.pack_forget()
            self.display_finances_monthly()
        elif view == "Yearly":
            self.summary_label.pack_forget()
            self.display_finances_yearly()
        elif view == "Summary":
            self.summary_label.pack(side="top")
            self.display_finances_summary()

    def display_finances_continuous(self) -> None:
        """Display daily finances view."""
        if self.canvas:
            # remove previous image
            matplotlib.pyplot.close(self.fig)
            self.canvas.get_tk_widget().pack_forget()

        dates = []
        prices = []

        self.fig, ax = matplotlib.pyplot.subplots()
        # Format the y-axis ticks to display a leading dollar sign.
        ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("$%d"))
        # Set the background color outside the chart border (where labels go)
        self.fig.set_facecolor(self.options["color_4"])
        # Set the background color inside the chart border
        ax.set_facecolor(self.options["color_4"])
        # Set axes visible
        ax.grid(color=self.options["color_1"], axis="y", alpha=0.2)

        # Requires that jobs_list is sorted, from oldest to newest job
        for job in self.jobs:
            job_date = str_to_date(job["end"])
            # Add the data point
            price = job["work_units"]
            ax.plot(job_date, price, "bo")

            dates.append(job_date)
            prices.append(price)
        ax.fill_between(dates, 0, prices, alpha=0.7)

        ax.set_ylabel("Revenue")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(
            side=tkinter.TOP, fill=tkinter.BOTH, expand=True
        )

        self.canvas.draw()

    def display_finances_monthly(self) -> None:
        """Display monthly finances view."""
        if self.canvas:
            # remove previous image
            matplotlib.pyplot.close(self.fig)
            self.canvas.get_tk_widget().pack_forget()

        dates = []
        prices = []

        self.fig, ax = matplotlib.pyplot.subplots()
        # Format the y-axis ticks to display a leading dollar sign.
        ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("$%d"))
        # Set the background color outside the chart border (where labels go)
        self.fig.set_facecolor(self.options["color_4"])
        # Set the background color inside the chart border
        ax.set_facecolor(self.options["color_4"])
        # Set axes visible
        ax.grid(color=self.options["color_1"], axis="y", alpha=0.2)

        # Requires that jobs_list is sorted, from oldest to newest job
        running_total = 0
        # The end date is used for collecting payment for a job.
        current_period = str_to_date(self.jobs[0]["end"]).month
        # previous_date = str_to_date(self.jobs[0]["end"])
        for job in self.jobs:
            job_date = str_to_date(job["end"])
            # if the date is a new year, reset the running total for the period
            if current_period != job_date.month:
                running_total = 0
                current_period = job_date.month

                # Sdd a dummy point after the last job in a period, so the
                # fill_between line goes straight down.
                prices.append(0)
                dates.append(
                    datetime.date(month=current_period, day=1, year=job_date.year)
                    + relativedelta(days=-1)
                )

                # Add a dummy point at the start of the new period, so the
                # fill_between goes to zero at the start of the new period.
                dates.append(
                    datetime.date(month=current_period, day=1, year=job_date.year)
                )
                prices.append(0)
            # Add the data point
            price = job["work_units"]
            total_price = price + running_total
            ax.plot(job_date, total_price, "bo")
            running_total += price

            dates.append(job_date)
            prices.append(total_price)
        ax.fill_between(dates, 0, prices, alpha=0.7)

        ax.set_ylabel("Revenue")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(
            side=tkinter.TOP, fill=tkinter.BOTH, expand=True
        )

    def display_finances_yearly(self) -> None:
        """Display finances yearly view."""
        if self.canvas:
            # remove previous image
            matplotlib.pyplot.close(self.fig)
            self.canvas.get_tk_widget().pack_forget()

        dates = []
        prices = []

        self.fig, ax = matplotlib.pyplot.subplots()
        # Format the y-axis ticks to display a leading dollar sign.
        ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("$%d"))
        # Set the background color outside the chart border (where labels go)
        self.fig.set_facecolor(self.options["color_4"])
        # Set the background color inside the chart border
        ax.set_facecolor(self.options["color_4"])
        # Set axes visible
        ax.grid(color=self.options["color_1"], axis="y", alpha=0.2)

        # Requires that jobs_list is sorted, from oldest to newest job
        running_total = 0
        total_price = 0
        # The end date is used for collecting payment for a job.
        current_period = str_to_date(self.jobs[0]["end"]).year
        for job in self.jobs:
            job_date = str_to_date(job["end"])
            # if the date is a new year, reset the running total for the period
            if current_period != job_date.year:
                running_total = 0
                current_period = job_date.year

                # Sdd a dummy point after the last job in a period, so the
                # fill_between line goes straight down.
                dates.append(
                    datetime.date(month=1, day=1, year=current_period)
                    + relativedelta(days=-1)
                )
                prices.append(total_price)

                # Add a dummy point at the start of the new period, so the
                # fill_between goes to zero at the start of the new period.
                dates.append(datetime.date(month=1, day=1, year=current_period))
                prices.append(0)
            # Add the data point
            price = job["work_units"]
            total_price = price + running_total
            ax.plot(job_date, total_price, "bo")
            running_total += price

            dates.append(job_date)
            prices.append(total_price)
        ax.fill_between(dates, 0, prices, alpha=0.7)

        ax.set_ylabel("Revenue")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(
            side=tkinter.TOP, fill=tkinter.BOTH, expand=True
        )

    def display_finances_summary(self):
        """Display annual/monthly text summary of finances."""
        self.summary_label.configure(text="Summary:")

        if self.canvas:
            # remove previous image
            matplotlib.pyplot.close(self.fig)
            self.canvas.get_tk_widget().pack_forget()

        # Create a dict of every month between the first and last job
        earliest_date = str_to_date(self.jobs[0]["end"])
        latest_date = str_to_date(self.jobs[-1]["end"])

        # map of datetime months (1-12) to string formats (jan-dec)
        print_month = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

        # zero out the days
        earliest_date = earliest_date.replace(day=1)
        latest_date = latest_date.replace(day=1)

        # Iterate through each month in this range, add it to a dict
        months_dict = {}
        while earliest_date <= latest_date:
            # Default value of zero, representing no jobs/revenue on this month
            months_dict[earliest_date] = 0
            earliest_date = earliest_date + relativedelta(months=+1)

        # Iterate through the jobs list and add the job revenue to the
        # corresponding month's revenue
        for job in self.jobs:
            job_date = str_to_date(job["end"]).replace(day=1)
            months_dict[job_date] += job["work_units"]

        # Print the monthly nad yearly revenue into a text label
        content = ""
        # make sure the dict is sorted (which it is based on insertion order)
        current_year = str_to_date(self.jobs[0]["end"]).year
        current_month = str_to_date(self.jobs[0]["end"]).month
        yearly_revenue = 0
        for revenue_period, revenue in months_dict.items():
            # If we have reached a new year...
            if revenue_period.year != current_year:
                # print the yearly summary and a blank line
                content += f"{current_year} Total: ${yearly_revenue}\n\n"

                # Reset the trackers and start collecting data on the new year
                current_year = revenue_period.year
                yearly_revenue = 0

            # Print and track the current month's revenue
            current_month = revenue_period.month
            content += f"{print_month[current_month - 1]}: ${revenue}\n"
            yearly_revenue += revenue

        # If we end on a month other than december, then print the yearly
        # summary so far
        if current_month != 12:
            content += f"{current_year} Total: ${yearly_revenue}"

        self.summary_label.configure(text=content)


class JobFrame(customtkinter.CTkFrame):
    """
    Handle the popup window when adding/viewing/modifying a job.

    Only one instance of this class should exist at a time.

    Parameters:
        master: the calling/root window/widget
        job_callback_func: Called when the user modifies/adds a job.
        job: a valid job dict.
            If None, the frame will create a new job.
            Else, the frame will load data from the specified job and modify it.
    """

    def __init__(
        self, master, job_callback_func, job_types: list, job: dict = None, **kwargs
    ):
        """Initialize all widgets."""
        super().__init__(master, **kwargs)

        if job:
            job_button_str = "Update Job"
            self.job_id = job["id"]
            logger.info(f"Opened update job frame for id {self.job_id}")
        else:
            job_button_str = "Add Job"
            self.job_id = 0
            logger.info(f"Opened add job frame for id {self.job_id}")
        self.job_callback_func = job_callback_func

        self.configure(border_width=5)

        self.name_entry = customtkinter.CTkEntry(self, placeholder_text="Client Name")
        self.name_entry.grid(row=0, column=0, padx=20, pady=5)

        self.phone_entry = customtkinter.CTkEntry(self, placeholder_text="Phone Number")
        self.phone_entry.grid(row=1, column=0, padx=20)

        customtkinter.CTkLabel(self, text="").grid(row=2, column=0, padx=20)

        self.price_entry = customtkinter.CTkEntry(self, placeholder_text="Price")
        self.price_entry.grid(row=3, column=0, padx=20)

        if len(job_types) > 0:
            self.job_type_menu = customtkinter.CTkOptionMenu(self, values=job_types)
            self.job_type_menu.set(job_types[0])
            self.job_type_menu.grid(row=4, column=0, padx=20)
        else:
            self.job_type_menu = customtkinter.CTkOptionMenu(
                self, values=["Other", "", "Add more job types in options"]
            )
            self.job_type_menu.set("Other")
            self.job_type_menu.grid(row=4, column=0, padx=20)

        customtkinter.CTkLabel(self, text="Notes").grid(row=5, column=0, padx=20)
        self.notes_textbox = customtkinter.CTkTextbox(self, width=200, height=85)
        self.notes_textbox.grid(row=6, column=0, padx=20)

        calendar_frame = customtkinter.CTkFrame(self)
        customtkinter.CTkLabel(calendar_frame, text="Start").grid(
            row=0, column=0, padx=5
        )
        customtkinter.CTkLabel(calendar_frame, text="End").grid(row=0, column=1, padx=5)
        self.start_date_entry = CTkDatePicker(calendar_frame)
        self.start_date_entry.grid(row=1, column=0, padx=5)
        self.end_date_entry = CTkDatePicker(calendar_frame)
        self.end_date_entry.grid(row=1, column=1, padx=5)
        calendar_frame.grid(row=7, column=0, padx=5, pady=5)

        self.start_date_entry.set_date(date.today())
        self.end_date_entry.set_date(date.today() + timedelta(days=7))

        self.start_date_entry.set_callback(self.calendar_event_handler)
        self.end_date_entry.set_callback(self.calendar_event_handler)

        self.info_label = customtkinter.CTkLabel(
            self, text=humanize.naturaldelta(timedelta(weeks=1))
        )
        self.info_label.grid(row=8, column=0, padx=5)

        button_frame = customtkinter.CTkFrame(self)
        self.modify_job_button = customtkinter.CTkButton(
            button_frame, text=job_button_str, command=self.update_job
        )
        self.modify_job_button.grid(row=0, column=0, padx=5)

        self.is_complete_check = customtkinter.CTkCheckBox(
            button_frame, text="Completed", command=self.update_info_label
        )
        self.is_complete_check.grid(row=0, column=1, padx=5)
        button_frame.grid(row=9, column=0, padx=5, pady=10)

        # If the user is viewing a job, then fill in the job's data
        if job:
            self.name_entry.insert(0, job["name"])
            self.phone_entry.insert(0, job["phone"])
            self.price_entry.insert(0, job["work_units"])
            self.job_type_menu.set(job["type"])
            self.notes_textbox.insert("0.0", job["notes"])
            self.start_date_entry.set_date(str_to_date(job["start"]))
            self.end_date_entry.set_date(str_to_date(job["end"]))
            if job["is_complete"]:
                self.is_complete_check.select()
            self.update_info_label()

            # Add a button to remove the existing job.
            self.remove_job_button = customtkinter.CTkButton(
                self, text="Remove Job", command=self.remove_job
            )
            self.remove_job_button.grid(row=10, column=0, padx=5, pady=10)

    def get_name_entry(self):
        """Get the tkinter widget associated with client name."""
        return self.name_entry._entry

    def get_phone_entry(self):
        """Get the tkinter widget associated with phone number."""
        return self.phone_entry._entry

    def get_price_entry(self):
        """Get the tkinter widget associated with job's price."""
        return self.price_entry._entry

    def calendar_event_handler(self, event: tkinter.Event = None) -> None:
        """Respond to user selecting a new start date."""
        logger.info("Calendar updated")
        self.update_info_label()

    def update_info_label(self) -> bool:
        """Update the text widget warning about potential issues with user input."""
        start = self.start_date_entry.get_date()
        end = self.end_date_entry.get_date()
        is_complete = self.is_complete_check.get()
        no_warnings_found = True
        notes_text = ""

        # If either of the dates are invalid,
        # state that and don't process the remaining date-based checks.
        if start is None:
            duration_text = "Invalid date"
            no_warnings_found = False
            notes_text += "\nWarning: Start date is invalid!"
        elif end is None:
            duration_text = "Invalid date"
            no_warnings_found = False
            notes_text += "\nWarning: End date is invalid!"
        else:
            # Process date-based checks
            duration = end - start
            if duration < timedelta(days=0):
                duration_text = "Less than 1 day"
                no_warnings_found = False
                notes_text += "\nWarning: Due date is earlier than start date!"
            elif duration < timedelta(days=1):
                duration_text = "Less than 1 day"
                notes_text += "\nNote: Job duration is less than 1 day."
            elif duration > timedelta(days=364):
                duration_text = f"{humanize.naturaldelta(duration)}"
                notes_text += "\nNote: Job duration is more than 1 year."
            else:
                duration_text = f"{humanize.naturaldelta(duration)}"
            if start - date.today() > timedelta(days=15):
                notes_text += "\nNote: Start date is 15 days after today."
            elif date.today() - start > timedelta(days=15) and self.job_id == 0:
                # Ignore this check if the job is marked as completed
                if not is_complete:
                    notes_text += "\nNote: Start date is 15 days before today."
            if end < date.today():
                notes_text += "\nNote: Due date is before today."

        # Check price / work units:
        # Strip off $ and cents
        price = self.price_entry.get().strip("$")
        decimal_index = price.find(".")
        if decimal_index != -1:
            price = price[:decimal_index]
        if str(price) == "":
            price = 0
        if not str(price).isnumeric() or int(price) < 0:
            no_warnings_found = False
            notes_text += "\nWarning: Price contains unexpected value!"

        # Print results to GUI
        if len(notes_text) > 0:
            duration_text = f"{duration_text}\n{notes_text}"
        self.info_label.configure(text=duration_text)
        # Fade out the submit job button if there are warnings
        if no_warnings_found:
            self.modify_job_button.configure(state="normal")
        else:
            self.modify_job_button.configure(state="disabled")

        # Toggle the drop-down calendar:
        # self.start_date_entry.drop_down()
        # This prevents the user clicking the add job button while a calendar is open.
        # However, this is a toggle, and it's annoying to get the state.
        # So instead the UI is such that it'd be difficult to press a button
        # while a calendar is open.

        return no_warnings_found

    def remove_job(self) -> None:
        """Send a signal to main app to remove the specified job."""
        # Send a confirmation window to the user
        if tkinter.messagebox.askokcancel(
            "Confirm Remove Job", "This action cannot be undone!"
        ):
            # The main window's function to update a job has a special case when
            # the job has a new member: 'marked_for_removal'.
            self.job_callback_func({"marked_for_removal": self.job_id})

    def update_job(self) -> None:
        """Verify data, then callback main app to update a job with supplied info."""
        # If the updating label didn't run into any warnings, continue adding the job
        if self.update_info_label():
            # Get input fields
            start = self.start_date_entry.get_date()
            end = self.end_date_entry.get_date()
            duration = end - start
            if duration < timedelta(days=0):
                tkinter.messagebox.showwarning(
                    "Unable to Add Job", "Due date is earlier than start date!"
                )
            else:
                name = self.name_entry.get()
                phone = self.phone_entry.get()

                # Strip off $ and cents
                price = self.price_entry.get().strip("$")
                decimal_index = price.find(".")
                if decimal_index != -1:
                    price = price[:decimal_index]
                if str(price) == "":
                    price = 0
                price = int(price)

                job_type = self.job_type_menu.get()
                notes = self.notes_textbox.get("1.0", "end-1c")
                is_complete = self.is_complete_check.get()
                if is_complete:
                    is_complete_str = "Complete"
                else:
                    is_complete_str = "Ongoing"
                if str(price) == "" or not str(price).isnumeric() or int(price) <= 0:
                    price = 0

                # Create a confirmation popup.
                job_str = (
                    f"Name: \t{name}\nPhone: \t{phone}\nPrice: \t${price}\nType:"
                    f" \t{job_type}\nNotes: \t{notes}\n\nStart Date:"
                    f" \t{start}\nDue Date: \t{end}\nJob Status:"
                    f" \t{is_complete_str}"
                )
                # Only add the job if user confirms it
                if tkinter.messagebox.askokcancel("Confirm Add Job", job_str):
                    job = {
                        "start": str(start),
                        "end": str(end),
                        "work_units": price,
                        "id": self.job_id,
                        "name": name,
                        "notes": notes,
                        "type": job_type,
                        "phone": phone,
                        "is_complete": is_complete,
                    }
                    self.job_callback_func(job)

    def fill_entries(self, name: str, phone: str):
        """Fill in the name/phone fields with the client's info."""
        logger.info(f"Job Frame: Filling in client ({name}, {phone})")
        self.name_entry.delete(0, tkinter.END)
        self.name_entry.insert(0, name)
        self.phone_entry.delete(0, tkinter.END)
        self.phone_entry.insert(0, phone)


class SearchFrame(customtkinter.CTkFrame):
    """
    Handle the popup window when searching for a job.

    Only one instance of this class should exist at a time.

    Parameters:
        master: the calling/root window/widget
        job_callback_func: The function to call when the user modifies/adds a job.
        job: a valid job dict.
            If None, the frame will load data from a blank template to create a new job.
            Else, the frame will load data from the specified job and modify it.
    """

    def __init__(self, master, **kwargs):
        """Initialize all widgets."""
        super().__init__(master, **kwargs)
        self.configure(border_width=5)

        self.name_entry = customtkinter.CTkEntry(self, placeholder_text="Client Name")
        self.name_entry.grid(row=0, column=0, padx=20, pady=5)

        self.phone_entry = customtkinter.CTkEntry(self, placeholder_text="Phone Number")
        self.phone_entry.grid(row=1, column=0, padx=20)

        customtkinter.CTkLabel(self, text="").grid(row=2, column=0, padx=20)

    def get_name_entry(self):
        """Get the tkinter widget associated with client name."""
        return self.name_entry._entry

    def get_phone_entry(self):
        """Get the tkinter widget associated with phone number."""
        return self.phone_entry._entry

    def fill_entries(self, name: str, phone: str):
        """Fill in the name/phone fields with the client's info."""
        logger.info(f"Search Frame: Filling in client ({name}, {phone})")
        self.name_entry.delete(0, tkinter.END)
        self.name_entry.insert(0, name)
        self.phone_entry.delete(0, tkinter.END)
        self.phone_entry.insert(0, phone)


class OptionsFrame(customtkinter.CTkFrame):
    """
    Handle the popup window when use is modifying options.

    Only one instance of this class should exist at a time.

    Parameters:
        master: The calling/root window/widget.
        options: The dict with current functions.
        save_options_callback_func: The function to call when the user saves options.
    """

    def __init__(self, master, options: dict, save_options, reset_options, **kwargs):
        """Initialize all widgets."""
        super().__init__(master, **kwargs)
        self.configure(border_width=5)
        self.save_options_callback = save_options
        self.reset_options_callback = reset_options

        customtkinter.CTkLabel(self, text="Window Name").grid(row=0, column=0, padx=20)
        self.window_name = customtkinter.CTkEntry(self)
        self.window_name.insert(0, options["window_name"])
        self.window_name.grid(row=0, column=1, padx=20, pady=5)

        self.grace_period_text = customtkinter.CTkLabel(
            self, text="Grace Period (days)"
        )
        self.grace_period_text.grid(row=1, column=0, padx=20)
        max_days = 10
        self.grace_period = customtkinter.CTkSlider(
            self,
            from_=0,
            to=max_days,
            number_of_steps=10,
            command=self.grace_period_slider,
        )
        self.grace_period.set(options["grace_period"].days)
        self.grace_period.grid(row=1, column=1, padx=20, pady=5)
        self.grace_period_slider(self.grace_period.get())

        self.work_units_text = customtkinter.CTkLabel(self, text="Work Units Per Day")
        self.work_units_text.grid(row=2, column=0, padx=20)
        max_work_units = 3000
        self.work_units = customtkinter.CTkSlider(
            self,
            from_=100,
            to=max_work_units,
            number_of_steps=int(max_work_units / 100) - 1,
            command=self.work_units_slider,
        )
        self.work_units.set(int(options["max_work_units_per_day"]))
        self.work_units.grid(row=2, column=1, padx=20, pady=5)
        self.work_units_slider(self.work_units.get())

        customtkinter.CTkLabel(self, text="Appearance Mode").grid(
            row=3, column=0, padx=20
        )
        self.appearance_mode = customtkinter.CTkOptionMenu(
            self, values=["system", "light", "dark"]
        )
        self.appearance_mode.set(options["appearance_mode"])
        self.appearance_mode.grid(row=3, column=1, padx=20, pady=5)

        customtkinter.CTkLabel(self, text="Accent Color").grid(row=4, column=0, padx=20)
        self.color_theme = customtkinter.CTkOptionMenu(
            self, values=["blue", "dark-blue", "green"]
        )
        self.color_theme.set(options["color_theme"])
        self.color_theme.grid(row=4, column=1, padx=20, pady=5)

        customtkinter.CTkLabel(
            self, text="Job Types:\n\n-Each line is a new type of job"
        ).grid(row=5, column=0, padx=20)
        self.type_textbox = customtkinter.CTkTextbox(self, width=150, height=150)
        # Convert the jobs list into a multi-line string
        job_type_str = "\n".join(options["job_types"])
        self.type_textbox.insert("0.0", job_type_str)
        self.type_textbox.grid(row=5, column=1, padx=20, pady=5)

        self.save_button = customtkinter.CTkButton(
            self, text="Save Changes", command=self.save_options
        )
        self.save_button.grid(row=6, column=0, padx=20, pady=10)
        self.reset_button = customtkinter.CTkButton(
            self, text="Reset", command=self.reset_options
        )
        self.reset_button.grid(row=6, column=1, padx=20, pady=10)

    def grace_period_slider(self, grace_period):
        """Configure text for grace period slider based on slider value."""
        self.grace_period_text.configure(text=f"Grace Period: {int(grace_period)} days")

    def work_units_slider(self, work_units):
        """Configure text for work units slider based on slider value."""
        self.work_units_text.configure(text=f"Work Units Per Day: {int(work_units)}")

    def save_options(self):
        """Send user-selected options to main window."""
        if tkinter.messagebox.askokcancel(
            "Save Changes?",
            "App will close after saving.\nOptions will take effect next time"
            " the app is opened.",
        ):
            # Convert the jobs list into a multi-line string
            job_types = []
            job_type_str = self.type_textbox.get("0.0", tkinter.END)
            job_type_str = job_type_str.split("\n")
            for job_type in job_type_str:
                job_type = job_type.strip("\n")
                if job_type != "":
                    job_types.append(job_type)

            # Create a new options structure and send it to the main app
            options = {
                "window_name": self.window_name.get(),
                "grace_period": timedelta(days=int(self.grace_period.get())),
                "max_work_units_per_day": float(self.work_units.get()),
                "appearance_mode": self.appearance_mode.get(),
                "color_theme": self.color_theme.get(),
                "job_types": job_types,
            }
            self.save_options_callback(options)

    def reset_options(self):
        """Reset all options to defaults."""
        if tkinter.messagebox.askokcancel(
            "Reset Options?",
            "App will close after saving.\nOptions will take effect next time"
            " the app is opened.",
        ):
            self.reset_options_callback()


class App(customtkinter.CTk):
    """
    Handle main window.

    Only one instance of this class should exist at a time.
    New windows should be instantiated from CTkToplevel().
    """

    def __init__(self):
        """
        Read in data from disc and open window at initial view.

        If data is missing, it will use default/empty data.
        """
        logger.info("Initializing main window...")

        # [General Members]
        self.jobs_file = pathlib.Path("data/jobs.json")
        self.backups_directory = pathlib.Path("data/backups")
        self.options_file = pathlib.Path("data/options.json")

        # [Chart Members]
        self.fig = None
        self.ax = None
        self.canvas = None
        self.toolbar = None
        # Mapping of job id's to their thin bars. Regenerated every chart refresh_view.
        self.id_to_bar = {}
        # Mapping of job id's to their y-location on the chart
        self.id_to_ydata = {}
        # Determines the center of the job start.
        self.ylim_start_job = None

        # Currently selected job on the chart
        self.selected_job = None
        self.selected_job_highlight = None
        self.selected_job_box = (0, 0, 0, 0)
        # Cache of jobs with a highlight due to being a search result
        self.searched_job_ids = []

        # Reference to widgets/frames/windows created dynamically at runtime
        self.job_frame = None
        self.suggestions_frame = None
        self.search_frame = None
        self.finance_window = None
        self.options_frame = None

        # Initialize core data structures
        self.options = self.load_options()
        self.jobs = self.load_jobs()
        self.convert_legacy_data()
        self.sort_jobs()
        self.client_database = ClientProfileDatabase(self.jobs)

        logger.info("Preparing initial chart view")
        self.date_to_work_units = {}
        self.compute_chart_data()
        self.generate_chart()
        self.update_tick_locator()

        logger.info("Creating tkinter main window")
        # These set the style to CTk widgets globally.
        # However, there should only be one CTk window anyways.
        # Themes: 'blue' (standard), 'green', 'dark-blue'
        customtkinter.set_default_color_theme(self.options["color_theme"])
        # Modes: 'system', 'light', 'dark'. On linux this always defaults to 'light'
        customtkinter.set_appearance_mode(self.options["appearance_mode"])

        # Initialize the tkinter window object
        super().__init__()

        self.geometry("1280x720")
        self.title(self.options["window_name"])

        # This custom handler inexplicably avoids errors where parts of the program
        # continue to loop infinitely even after the user closes the window, forcing
        # the program to be shut down via closing the terminal.
        # This issue appears to come up when you have both a tkinter window
        # and a matplotlib chart both updating:
        # https://github.com/TomSchimansky/CustomTkinter/issues/963
        self.protocol("WM_DELETE_WINDOW", self.on_quit)

        self.bind("<Key>", self.key_press_handler)

        self.set_style()

        self.nav_bar_frame = customtkinter.CTkFrame(self)
        self.open_finances_button = customtkinter.CTkButton(
            self.nav_bar_frame, text="View Finances", command=self.toggle_finance_window
        )
        self.open_job_button = customtkinter.CTkButton(
            self.nav_bar_frame, text="Add Job", command=self.toggle_job_window
        )
        self.open_search_button = customtkinter.CTkButton(
            self.nav_bar_frame, text="Search Jobs", command=self.toggle_search_window
        )
        self.reset_chart_button = customtkinter.CTkButton(
            self.nav_bar_frame, text="Recenter Chart", command=self.reset_chart_view
        )
        self.open_options_button = customtkinter.CTkButton(
            self.nav_bar_frame, text="Options", command=self.toggle_options_window
        )
        self.open_finances_button.grid(row=0, column=0, padx=20, pady=20)
        self.open_job_button.grid(row=0, column=1, padx=20, pady=20)
        self.open_search_button.grid(row=0, column=2, padx=20, pady=20)
        self.reset_chart_button.grid(row=0, column=3, padx=20, pady=20)
        self.open_options_button.grid(row=0, column=4, padx=20, pady=20)
        self.nav_bar_frame.pack(side=tkinter.TOP)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().configure(
            background=self.options["color_5"],
            highlightcolor=self.options["color_5"],
            highlightbackground=self.options["color_5"],
        )
        self.canvas.draw()
        # pack_toolbar=False: makes it easier to use a layout manager later on
        self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        self.toolbar.update()

        # Handle when the user clicks on (selects) a bar on the chart
        self.canvas.mpl_connect("pick_event", self.pick_handler)
        # Handle when user zooms in/out via the mouse scroll wheel
        self.canvas.mpl_connect("scroll_event", self.scroll_zoom_handler)

        # Packing order is important. Widgets are processed sequentially and if there
        # is no space left, because the window is too small, they are not displayed.
        # The canvas is rather flexible in its size, so we pack it last which makes
        # sure the toolbar controls are displayed.
        self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(
            side=tkinter.TOP, fill=tkinter.BOTH, expand=True
        )
        logger.info("Finished initializing main window.")

    def toggle_finance_window(self):
        """Toggle the window displaying finances."""
        if self.finance_window is None or not self.finance_window.winfo_exists():
            logger.info("Opened finances window")
            self.finance_window = FinanceWindow(self.jobs, self.options)
        else:
            logger.info("(NYI) Destroyed finances window")
            # Focus existing window
            self.finance_window.focus()

    def toggle_job_window(self, job: dict = None):
        """Toggle the Add Job window open/closed."""
        if self.job_frame:
            self.destroy_job_frame()
        else:
            # Close other frames
            if self.search_frame or self.options_frame:
                self.destroy_job_frame()

            if job:
                logger.info(f"  Opened job frame (existing job {job['id']})")
                self.job_frame = JobFrame(
                    master=self,
                    job_types=self.options["job_types"],
                    job_callback_func=self.update_job_handler,
                    job=job,
                )
            else:
                logger.info("  Opened job frame (new job)")
                self.job_frame = JobFrame(
                    master=self,
                    job_types=self.options["job_types"],
                    job_callback_func=self.add_job_handler,
                )
            self.job_frame.place(relx=0.9, rely=0.1, anchor="ne")

    def toggle_search_window(self):
        """Toggle the search job window open/closed."""
        if self.search_frame:
            self.destroy_job_frame()
        else:
            # Close other frames
            if self.job_frame or self.options_frame:
                self.destroy_job_frame()

            logger.info("Opened search frame")
            self.search_frame = SearchFrame(master=self)
            self.search_frame.place(relx=0.9, rely=0.1, anchor="ne")

    def toggle_options_window(self):
        """Toggle the options window open/closed."""
        if self.options_frame:
            self.destroy_job_frame()
        else:
            # Close other frames
            if self.job_frame or self.search_frame:
                self.destroy_job_frame()
            logger.info("Opened options frame")
            self.options_frame = OptionsFrame(
                self, self.options, self.update_options, self.reset_options
            )
            self.options_frame.place(relx=0.9, rely=0.1, anchor="ne")

    def update_job_handler(self, job: dict):
        """Modify or remove an existing job."""
        self.destroy_job_frame()
        # Special case where job should be removed
        if "marked_for_removal" in job.keys():
            job_id = job["marked_for_removal"]
            existing_job = self.jobs[job_id]
            logger.info(f"  Removing existing Job: {existing_job}")
            self.jobs.pop(job_id)
        else:
            logger.info("  Updating Job")
            job_id = job["id"]
            existing_job = self.jobs[job_id]
            logger.info(f"    Existing Job: {existing_job}")
            logger.info(f"    User-submitted Job: {job}")
            # Find and update the existing job
            for key, val in job.items():
                # This check is only here for debugging purposes
                if existing_job[key] != val:
                    logger.info(f"    Updating {key}: {existing_job[key]} -> {val}")
                self.jobs[job_id][key] = val

            logger.info(f"    Updated Job: {self.jobs[job_id]}")
            # if the client's name/phone have changed,
            #  remove the old entry from the database.
            self.client_database.add_client_to_database((job["name"], job["phone"]))

        # Update the display.
        self.destroy_job_frame()
        self.sort_jobs()
        self.save_jobs()

        # Refresh Canvas Visuals
        self.compute_chart_data()
        self.generate_chart()
        # By default, the canvas only updates it's visuals if it receives an event call.
        # We've changed the chart data outside an event handler,
        # so manually tell the chart canvas to update its visual display.
        self.update_tick_locator()
        self.fig.canvas.draw_idle()

    def destroy_job_frame(self):
        """Destroy the job frame and the job highlight."""
        if self.selected_job_highlight:
            # Remove chart plot data that produces the highlight
            logger.info("  Destroyed job highlight")
            self.selected_job = None
            self.selected_job_highlight.remove()
            self.selected_job_highlight = None
            self.fig.canvas.draw_idle()
        if self.job_frame:
            logger.info("  Destroyed job frame")
            self.job_frame.destroy()
            self.job_frame = None
        if self.suggestions_frame:
            self.suggestions_frame.destroy()
            self.suggestions_frame = None
        if self.search_frame:
            self.search_frame.destroy()
            self.search_frame = None
        if self.options_frame:
            self.options_frame.destroy()
            self.options_frame = None
        # For jobs highlighted due to showing up in a search,
        # we preserve the highlights for one iteration of this destroy function.
        # This means the highlight is visible after closing the search frame,
        # but disappears the next time any frame is opened.
        # self.clear_job_search_highlights()

    def add_job_handler(self, job: dict):
        """Add a new job from supplied info."""
        self.destroy_job_frame()

        job["id"] = len(self.jobs)
        logger.info(f"  Adding Job {job}")

        # Add the new job.
        self.jobs.append(job)
        self.client_database.add_client_to_database((job["name"], job["phone"]))

        # Update the display
        self.destroy_job_frame()
        self.sort_jobs()
        self.save_jobs()

        # Refresh Canvas Visuals
        self.compute_chart_data()
        self.generate_chart()
        # By default, the canvas only updates it's visuals if it receives an event call.
        # We've changed the chart data outside an event handler,
        # so manually tell the chart canvas to update its visual display.
        self.update_tick_locator()
        self.fig.canvas.draw_idle()

    def update_options(self, options: dict):
        """Modify options from supplied info."""
        logger.info("Modifying Options:")
        for key, val in options.items():
            # This check is only here for debugging purposes
            if self.options[key] != val:
                logger.info(f"  Updating {key}: {self.options[key]} -> {val}")
            self.options[key] = val
        self.save_options()
        # Close/Restart the app
        self.on_quit()

    def reset_options(self):
        """Reset all options."""
        logger.info("Resetting options")
        self.destroy_job_frame()
        if os.path.exists(self.options_file):
            try:
                os.remove(self.options_file)
                logger.info(f"  '{self.options_file}' deleted successfully.")
            except FileNotFoundError:
                print(f"Error: File '{self.options_file}' not found.")
            except PermissionError:
                print(f"Error: Permission denied to delete '{self.options_file}'.")
            except OSError as e:
                print(f"Error deleting file '{self.options_file}': {e}")
        # Load and save to disk the default options
        self.load_options()
        # Close/Restart the app
        self.on_quit()

    def save_options(self):
        """Save the options data structure to disk."""
        logger.info("Saving options.json")
        with open(self.options_file, mode="wt", encoding="UTF-8") as out_file:
            # Convert python-exclusive objects to JSON-ready objects before saving.
            self.options["grace_period"] = self.options["grace_period"].days
            out_file.write(json.dumps(self.options, sort_keys=True, indent=4))
            # Convert these objects to python-ready objects.
            self.options["grace_period"] = timedelta(
                days=int(self.options["grace_period"])
            )

    def save_jobs(self):
        """Save the jobs list to disk, making a backup of the previous list."""
        # Store a backup of the prior job data, if it exists
        if self.jobs_file.is_file():
            # The int conversion truncates the timestamp to the nearest second.
            backup_filename = f"{int(time.time())}.json"
            logger.info(f"  Saving backup {backup_filename}")
            shutil.move(self.jobs_file, self.backups_directory / backup_filename)

        # Save job data to disk
        logger.info("  Saving jobs.json")
        with open(self.jobs_file, mode="wt", encoding="UTF-8") as out_file:
            out_file.write(json.dumps(self.jobs, sort_keys=True, separators=(",", ":")))

        prune_files_in_dir(self.backups_directory, NUM_BACKUPS)

    def load_options(self) -> dict:
        """Read in options from an existing file.

        Generates a default options file if no options file was found.
        """
        if os.path.exists(self.options_file):
            logger.info("Reading existing options.json")
            with open(self.options_file, mode="rt", encoding="UTF-8") as in_file:
                options = json.loads(in_file.read())
            logger.info(f'Read in data from version {options["version_number"]}')
        else:
            logger.info("Unable to find options.json. Generating new options.json")
            options = {
                "version_number": CURRENT_VERSION,
                "window_name": "Horizon",
                "grace_period": 2,
                "max_work_units_per_day": 300.0,
                "color_theme": "dark-blue",
                "appearance_mode": "dark",
                "job_types": ["Other", "Add more job types in options"],
                "bar_height": 1.0,
                "bar_y_pos_step": 1.0,
                "color_1": "#03045e",
                "color_2": "#0077b6",
                "color_3": "#00b4d8",
                "color_4": "#90e0ef",
                "color_5": "#caf0f8",
            }
            with open(self.options_file, mode="wt", encoding="UTF-8") as out_file:
                out_file.write(json.dumps(options, indent=4))
        # Color 1: Text
        # color_2: Chart Short Bars (thick bars indicating how long a job is budgeted)
        # color_3: Chart Long Bars (transparent bars indicating start/end dates)
        # color_4: Chart background
        # color_5: Pane background (when there's no widgets covering up area)

        # Convert certain options from text into python-ready formats
        options["grace_period"] = timedelta(days=int(options["grace_period"]))
        return options

    def load_jobs(self) -> list:
        """Read in jobs data from disk, or generate a default jobs file if missing."""
        if os.path.exists(self.jobs_file):
            logger.info("Reading existing jobs.json")
            with open(self.jobs_file, mode="rt", encoding="UTF-8") as in_file:
                jobs = json.loads(in_file.read())
        else:
            logger.info("Unable to find jobs.json. Generating new jobs.json")
            today = datetime.date.today()
            next_week = today + timedelta(days=7)
            jobs = [
                {
                    "end": date_to_str(next_week),
                    "id": 0,
                    "is_complete": False,
                    "name": "Example Client",
                    "notes": "",
                    "phone": "+1 (123) 456-7890",
                    "start": date_to_str(today),
                    "type": "Misc",
                    "work_units": 1000,
                }
            ]
            with open(self.jobs_file, mode="wt", encoding="UTF-8") as out_file:
                out_file.write(json.dumps(jobs, indent=4))
        return jobs

    def convert_legacy_data(self) -> None:
        """Convert existing job data from an older version."""
        if self.options["version_number"] != CURRENT_VERSION:
            logger.info(
                f"Updating to new version {CURRENT_VERSION} from old version"
                f" {self.options['version_number']}..."
            )

            # Version 24 changes
            if self.options["version_number"] < 24:
                for job in self.jobs:
                    # v23 -> v24 notes are an expected element of all jobs.
                    if "notes" not in job.keys():
                        job["notes"] = ""
                    # v23 -> v24 work_units are now stored as ints (not a str).
                    if isinstance(job["work_units"], str):
                        job["work_units"] = int(job["work_units"])
                self.save_jobs()

            self.options["version_number"] = CURRENT_VERSION
            logger.info(f"Finished updating to new version {CURRENT_VERSION}")

    def sort_jobs(self) -> None:
        """
        Sort jobs by due date (earliest to latest).

        Resets job id's so that their id == index in list
        """
        self.jobs = sorted(self.jobs, key=lambda v: v["end"])
        for index, job in enumerate(self.jobs):
            job["id"] = index

    def compute_chart_data(self) -> None:
        """
        Recalculate job data for a new chart.

        Requires:
            self.jobs is sorted.
        """
        # Find the right-side x-bound of the chart.
        latest_due_date = str_to_date(self.jobs[-1]["end"])

        # Create a dict, with a key each day ranging from
        # a month before the earliest incomplete job's end date
        # to the latest end date of any job.
        # The values represent the budgeted work-units per day to complete all tasks
        # on-time.
        earliest_date = date.today() - timedelta(days=30)
        self.date_to_work_units.clear()
        for job in self.jobs:
            if not job["is_complete"]:
                earliest_date = str_to_date(job["end"]) - timedelta(days=30)
                break
        current_date = latest_due_date + timedelta(days=1)
        while current_date >= earliest_date:
            current_date -= timedelta(days=1)
            self.date_to_work_units[current_date] = []

        # Initialize each job into the jobs_dict:
        # Add each {'job_id': 'work_units'} pair, to 2 days (grace period) before it's
        # set end date
        for job in self.jobs:
            # Only gather budgeted time data for jobs that are unfinished
            if job["is_complete"]:
                continue
            end_date = str_to_date(job["end"]) - self.options["grace_period"]
            self.date_to_work_units[end_date].append(
                (job["id"], float(job["work_units"]))
            )

        # Scan backwards through the dict, feed-forwarding the remaining unmet work
        max_work_units_in_a_day = self.options["max_work_units_per_day"]
        # The default traversal order is insertion order, which is from the latest to
        # the earliest date in this case
        for day, job_list in self.date_to_work_units.items():
            total_units = 0
            for job_id, work_units in job_list:
                total_units += work_units
            # If there are more work units in this day than the max, feed the remaining
            # to the next day to be processed
            if total_units > max_work_units_in_a_day:
                avg_units_per_job = max_work_units_in_a_day / len(job_list)
                previous_day = day - timedelta(days=1)
                for job_id, work_units in job_list:
                    # Subtract the average budgeted work_units from each job.
                    # If the job still has unmet work_units, feed it to the previous day
                    remaining_units = work_units - avg_units_per_job
                    if remaining_units > 0:
                        self.date_to_work_units[previous_day].append(
                            (job_id, remaining_units)
                        )

    def generate_chart(self) -> None:
        """
        Plot data for a new chart.

        Requires:
            self.jobs has been sorted.
            self.date_to_work_units has been generated.
        """
        # Now convert the data in preparation for chart data.
        # label = client name, y = (start_date, duration_time)

        if not self.fig:
            logger.info("Initializing chart for the first time...")
            self.fig, self.ax = matplotlib.pyplot.subplots()
            self.fig.set_size_inches(8, 8)
            # Set the background color outside the chart border (where the labels are)
            self.fig.set_facecolor(self.options["color_4"])
            # Set the background color inside the chart border
            self.ax.set_facecolor(self.options["color_4"])

        else:
            logger.info("Refreshing chart...")
            self.ax.cla()

        # Reset map of job id's to their thin bars
        self.id_to_bar.clear()
        self.id_to_ydata.clear()

        # Set axes visible
        self.ax.grid(color=self.options["color_1"], axis="x", alpha=0.2)

        # Collect the list of y-axis labels (the job descriptions, i.e. client names)
        name_labels = []
        # Store some markers for use with the legend
        lines = []
        labels = []
        # Plot each line of data/job on the chart at staggered y intervals
        next_bar_y_pos = -0.25
        # Set the margins, so the job selection hitbox is accurate across varied numbers
        # of charted jobs
        if len(self.jobs) == 0:
            margin_y_pad = 0
        else:
            margin_y_pad = 0.25 * self.options["bar_height"] / len(self.jobs)
        matplotlib.pyplot.margins(y=margin_y_pad)

        # Store of the job closest to a few days before today.
        # Used for ylim calculations later.
        # ylim_start_date = date.today() - self.options['grace_period']
        self.ylim_start_job = None
        for job in self.jobs:
            start_date = str_to_date(job["start"])
            end_date = str_to_date(job["end"])

            # Skip over jobs that ended a while before today
            if end_date <= date.today() - timedelta(days=OLD_JOB_THRESHOLD):
                logger.info(f"Skipped Plotting Job {job["name"]}: {job["type"]}")
                continue

            # Store the first job with an end date a little bit before today
            if self.ylim_start_job is None:
                if end_date >= date.today() - timedelta(days=1):
                    self.ylim_start_job = next_bar_y_pos

            # This is what shows up on the y-axis to describe a job
            name_labels.append(job["name"])

            duration = end_date - start_date
            plot_data = (start_date, duration)
            # matplotlib expects a list of tuples as the input data, even if the list is
            # a single element
            plot_data = [plot_data]
            # Plot a thin line from the start/end of the job
            y_bar_height = (
                next_bar_y_pos + (self.options["bar_height"] / 8),
                self.options["bar_height"] / 4,
            )
            # pick radius: There are 72 pixels per screen inch
            self.id_to_bar[str(job["id"])] = self.ax.broken_barh(
                plot_data,
                y_bar_height,
                color=self.options["color_3"],
                alpha=0.3,
                picker=True,
                pickradius=5,
                label=f"{job['id']}",
                linestyle="-",
                edgecolor=self.options["color_1"],
                capstyle="round",
                linewidth=0,
            )
            self.id_to_ydata[str(job["id"])] = y_bar_height[0]

            # Plot a thick line based on the estimated work_units of the job
            # (only if the job is ongoing)
            if not job["is_complete"]:
                latest_scanned_date = end_date - self.options["grace_period"]
                # Scan the dates_dict until we find the end of budgeted days
                job_id = job["id"]
                while True:
                    continue_iter = False
                    for tup in self.date_to_work_units[latest_scanned_date]:
                        if tup[0] == job_id:
                            continue_iter = True
                    if not continue_iter:
                        break
                    latest_scanned_date -= timedelta(days=1)
                dura = (end_date - self.options["grace_period"]) - latest_scanned_date
                plot_data = [(latest_scanned_date, dura)]

                # This plots a long, flat thick line representing budgeted work days to
                # complete the job
                if len(lines) == 0:
                    lines.append(
                        self.ax.broken_barh(
                            plot_data,
                            (next_bar_y_pos, self.options["bar_height"] / 2),
                            color=self.options["color_2"],
                        )
                    )
                    labels.append("Ongoing")
                else:
                    self.ax.broken_barh(
                        plot_data,
                        (next_bar_y_pos, self.options["bar_height"] / 2),
                        color=self.options["color_2"],
                    )
            # Complete jobs get a alternate appearance for their budgeted days
            elif job["is_complete"]:
                # This plots a long, flat thick line.
                # 1 day on chart = about 200 price units; does not consider other jobs.
                dura = max(1, math.floor(int(job["work_units"]) / 200))
                dura = timedelta(days=dura)
                plot_data = [
                    (
                        str_to_date(job["end"]) - dura - self.options["grace_period"],
                        dura,
                    )
                ]
                if len(lines) == 1:
                    lines.append(
                        self.ax.broken_barh(
                            plot_data,
                            (next_bar_y_pos, self.options["bar_height"] / 2),
                            color=self.options["color_5"],
                            alpha=0.7,
                        )
                    )
                    labels.append("Complete")
                else:
                    self.ax.broken_barh(
                        plot_data,
                        (next_bar_y_pos, self.options["bar_height"] / 2),
                        color=self.options["color_5"],
                        alpha=0.7,
                    )

            # Place the text to the right-side grace period, on the thin line
            x = plot_data[0][0] + plot_data[0][1] + self.options["grace_period"]
            y = y_bar_height[0]
            annotate_text = job["name"]
            if "type" in job.keys():
                annotate_text += f": {job['type']}"
            # Complete jobs have their annotations placed a bit more to the left
            if job["is_complete"]:
                x = plot_data[0][0] + plot_data[0][1] + self.options["grace_period"]
            self.ax.annotate(
                xy=(x, y),
                text=annotate_text,
                ha="left",
                va="center",
                color="black",
                fontsize=12,
                annotation_clip=False,
                clip_on=True,
            )
            # Prepare for next line of data
            next_bar_y_pos += self.options["bar_y_pos_step"]

        # If there is no job ending after today, set the initial y view to the last job
        if self.ylim_start_job is None:
            self.ylim_start_job = next_bar_y_pos

        # Configure general chart properties
        self.ax.set_xlim(
            date.today() + timedelta(days=20), date.today() - timedelta(days=2)
        )
        self.ax.invert_xaxis()
        self.ax.xaxis.set_ticks_position("top")
        self.ax.set_yticks(range(len(name_labels)), labels=name_labels)

        # Y lim:
        # By default, the chart shrinks the y-axis in order to show ALL plotted jobs.
        # However, we've plotted each job exactly 1.0 y-units apart.
        # If we want to show only 10 jobs on the y-axis labels,
        # then we can set the y lims to (i, i+10).
        # So, how to select i?
        # Jobs are sorted by their end date. Find the job with an end date
        # nearest/slightly before today.
        # Then, grab that job plus the desired number of jobs after it.
        self.ax.set_ylim(self.ylim_start_job, self.ylim_start_job + 15)
        self.ax.invert_yaxis()

        # Create a legend explaining the different colorings used for ongoing and
        # complete jobs.
        labels = ["Ongoing", "Complete"]
        # facecolor=self.options['color_5']
        self.ax.legend(
            lines,
            labels,
            fancybox=True,
            shadow=True,
            loc="upper right",
            facecolor="#97e5f7",
            draggable=False,
        )

        # self.fig.tight_layout()
        logger.info("Finished generating chart")

    def set_style(self) -> None:
        """Set visual appearance of ttk widgets."""
        # CTk widgets use a different style from the ttk.Style widgets.
        # Therefore, any changes to ttk.Style only apply to non-CTk objects
        # (DateEntry in this project).
        style = ttk.Style(self)
        style.theme_use("clam")

        # Dark mode CTk colors:
        # #8F9D9E: light grey; text on dark background.
        # #565B5E: medium-light grey; border.
        # #343638: medium grey; background field entry.
        # #212121: dark grey; non-interactive element background.

        # Light mode CTk colors:
        # #958685: medium grey; text on light background
        # #979DA2: medium-light grey; border.
        # #F9F9FA: white; background field entry.
        # #E5E5E5: dark grey; non-interactive element background.

        # DateEntry style elements:
        # foreground: text color
        # fieldbackground: entry box color
        # background: clickable arrow box background color
        # no effect: border (color), borderwidth (int), highlightcolor (color),
        # highlightbackground (color)

        if self.options["appearance_mode"] == "dark":
            logger.info("Set style to dark")
            style.configure(
                "Custom.DateEntry",
                foreground="#8F9D9E",
                fieldbackground="#343638",
                background="#565B5E",
            )
        else:
            logger.info("Set style to light")
            style.configure(
                "Custom.DateEntry",
                foreground="#958685",
                fieldbackground="#F9F9FA",
                background="#979DA2",
            )

    def scroll_zoom_handler(self, event):
        """Use the scroll wheel to zoom in/out of the chart."""
        # Axes: Affects only x-axis.
        # Variable: Responds to mouse location.
        #  Zooms in towards mouse location.
        #  Zooms out from center of chart view.

        # Determine if we zoom in (up) or out (down)
        if event.button == "up":
            # Xlim will be the start date and end date of the current range
            lim = self.ax.get_xlim()
            duration = lim[1] - lim[0]

            # Don't zoom in if below a threshold.
            # MPL plots year/month/day for any duration above about 7-10 days.
            # <7 days, and it starts labelling hours, which isn't useful data.
            # A minimum value of 10-30 days seems visually presentable.
            if duration < 20:
                return
            # Zoom in by a factor of 2, then split this change among the start/end xlims
            duration = duration / 4.0

            # Use a lerp to split the duration among the start/end dates.
            lerp_split = lerp(
                0.0, duration, event.x / self.canvas.get_tk_widget().winfo_width()
            )
            self.ax.set_xlim((lim[0] + lerp_split, lim[1] - (duration - lerp_split)))

        else:
            lim = self.ax.get_xlim()
            duration = lim[1] - lim[0]

            # Don't zoom out if above a threshold (about 1 year)
            if duration > 200:
                return
            duration = duration / 2.0

            # Use a lerp to split the duration among the start/end dates.
            self.ax.set_xlim((lim[0] - duration, lim[1] + duration))

        # Refresh chart visuals
        self.update_tick_locator()
        self.fig.canvas.draw_idle()

    def pick_handler(self, event):
        """Respond to user clicking on chart elements."""
        # If the user picked data on the chart.
        # if type(event.artist) == matplotlib.legend.Legend:
        #    return
        # Ignore user actions with objects that aren't the plotted jobs.
        if (
            isinstance(event.artist, matplotlib.collections.PolyCollection)
            and event.mouseevent.button == 1
        ):
            pick_id = int(event.artist.get_label())
            logger.info(f"Pick Event: {pick_id}...")

            # If the user clicked on the plot they already selected, close the box.
            if self.selected_job and pick_id == self.selected_job["id"]:
                self.destroy_job_frame()
            # Else, highlight the new job
            else:
                # Close existing job window and highlight
                self.destroy_job_frame()

                # Get the job with picked id
                job = self.jobs[pick_id]

                logger.info(f"  Selected job {pick_id}: {job}")
                self.selected_job = job
                # Plot the new highlight and open the job details view.

                # Move the plotted selection line.
                start_date = str_to_date(self.selected_job["start"])
                end_date = str_to_date(self.selected_job["end"])

                duration = end_date - start_date
                # plot_data tuples are of the form (start_date, duration).
                plot_data = (start_date, duration)
                # the charts expect a list of tuples as the input data.
                plot_data = [plot_data]
                # Plot a thin line from the start/end of the job.
                y_data = round(event.mouseevent.ydata)
                y_bar_height = (
                    y_data - (self.options["bar_height"] / 2),
                    self.options["bar_height"] / 1,
                )
                self.selected_job_highlight = self.ax.broken_barh(
                    plot_data, y_bar_height, color=self.options["color_3"], alpha=0.5
                )
                self.fig.canvas.draw_idle()
                self.toggle_job_window(job)

    def update_tick_locator(self):
        """Set x-axis ticks to a custom format."""
        lim = self.ax.get_xlim()
        duration = lim[1] - lim[0]
        if duration <= 30:
            # If the current view of the plot covers less than 30 days, label each day.
            self.ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))
        else:
            # If the current view of the plot covers over a month, use the concise date
            # labels
            self.ax.xaxis.set_major_locator(
                matplotlib.dates.AutoDateLocator(minticks=3, maxticks=7)
            )

    def key_press_handler(self, event):
        """Handle user key press events."""
        # Ignore shift
        if event.keycode in keycodes["shift"]:
            logger.info(f"Key press event: {event.keycode} -> Shift")
        else:
            logger.info(f"Key press event: {event.keycode} -> {event.char}")

        # Send the event to the job frame window
        if self.job_frame:
            # If the focus/currently selected widget is the name/phone entries,
            # display suggested clients
            if (
                event.widget == self.job_frame.get_name_entry()
                or event.widget == self.job_frame.get_phone_entry()
            ):
                name = self.job_frame.name_entry.get()
                phone = self.job_frame.phone_entry.get()
                button_data = self.client_database.get_matching_clients(name, phone)
                # Place the suggested clients frame on the left side of the job frame
                x_loc = self.job_frame.winfo_rootx() - self.winfo_x()
                y_loc = self.job_frame.winfo_rooty() - self.winfo_y()
                self.update_suggestions_frame(
                    x_loc, y_loc, self.job_frame_suggestion_button_handler, button_data
                )
            # If the focus is on the price entry, check if input is a number.
            if event.widget == self.job_frame.get_price_entry():
                self.job_frame.update_info_label()
        # Send the event to the search frame window
        elif self.search_frame:
            # If the focus/currently selected widget is the name/phone entries,
            # display suggested clients
            if (
                event.widget == self.search_frame.get_name_entry()
                or event.widget == self.search_frame.get_phone_entry()
            ):
                name = self.search_frame.name_entry.get()
                phone = self.search_frame.phone_entry.get()
                button_data = self.client_database.get_matching_clients(name, phone)
                # Place the suggested clients frame on the left side of the job frame
                x_loc = self.search_frame.winfo_rootx() - self.winfo_x()
                y_loc = self.search_frame.winfo_rooty() - self.winfo_y()
                self.update_suggestions_frame(
                    x_loc,
                    y_loc,
                    self.search_frame_suggestion_button_handler,
                    button_data,
                )

    def update_suggestions_frame(
        self,
        x: int,
        y: int,
        button_callback_func,
        button_data: list = None,
    ) -> None:
        """Open suggestions frame."""
        # Close the existing frame
        if self.suggestions_frame:
            self.suggestions_frame.destroy()
        # If there is data to supply, then open a new frame
        if len(button_data) != 0:
            self.suggestions_frame = SuggestionsFrame(
                self, button_callback_func=button_callback_func, button_data=button_data
            )
            self.suggestions_frame.place(x=x, y=y, anchor="ne")

    def job_frame_suggestion_button_handler(self, client):
        """Fill in the name and phone of the job frame fields with the client's info."""
        if self.job_frame:
            self.job_frame.fill_entries(client[0], client[1])
        # Close suggestions
        if self.suggestions_frame:
            self.suggestions_frame.destroy()
            self.suggestions_frame = None

    def search_frame_suggestion_button_handler(self, client):
        """Open a suggestions frame showing jobs from a client's info."""
        # Fill in the current name/phone entries
        self.search_frame.fill_entries(client[0], client[1])

        # Close current suggestions
        if self.suggestions_frame:
            self.suggestions_frame.destroy()
            self.clear_job_search_highlights()
        # Get jobs associated with specified client
        client_jobs = []
        for job in self.jobs:
            if job["name"] == client[0] and job["phone"] == client[1]:
                client_jobs.append(job)

        # Chart: display highlights on all jobs matched this client
        for job in client_jobs:
            # Get the thin bar belonging to this job (if it was plotted)
            job_id = str(job["id"])
            if job_id in self.id_to_bar:
                # Add a dark blue dashed ring about the bar and increase its alpha.
                matplotlib.pyplot.setp(
                    self.id_to_bar[job_id],
                    linestyle="--",
                    linewidth=2,
                    edgecolor=self.options["color_1"],
                    capstyle="round",
                    alpha=0.5,
                )
                # Cache the id so we can quickly remove the highlight later
                self.searched_job_ids.append(job["id"])
        self.fig.canvas.draw_idle()

        # Open a suggestions frame listing jobs from this client.
        # don't display anything if there are no jobs associated with this client
        if len(client_jobs) > 0:
            # Place the suggested jobs frame fon the left side of the search frame
            x_loc = self.search_frame.winfo_rootx() - self.winfo_x()
            y_loc = self.search_frame.winfo_rooty() - self.winfo_y()
            self.update_suggestions_frame(
                x_loc, y_loc, self.search_job_button, client_jobs
            )

    def search_job_button(self, job: dict):
        """Change chart view to center on a searched job."""
        self.destroy_job_frame()
        logger.info("Searching for job %s %s", job["name"], job["work_units"])
        # Change the xlims to zoom in about this job.
        # May also need to change y-lims.

        # Close existing job window and highlight
        self.destroy_job_frame()

        # Get the job with picked id
        self.toggle_job_window(job)

        logger.info(f"  Selected job via search: {job}")
        self.selected_job = job

        # If the job wasn't plotted, don't update graph lims
        if str(job["id"]) not in self.id_to_ydata:
            logger.info(
                "  Selected job was not plotted, skipped updating chart visuals"
            )
            self.clear_job_search_highlights()
            return

        # Zoom in to 1.5 weeks before/after the end date of this job.
        end_date = str_to_date(job["end"])
        self.ax.set_xlim(end_date + timedelta(days=6), end_date - timedelta(days=16))
        self.ax.invert_xaxis()

        # Change the ylims to center on this job.
        ylim_center = self.id_to_ydata[str(job["id"])]
        self.ax.set_ylim(ylim_center - 7, ylim_center + 8)
        self.ax.invert_yaxis()

        # Reset entry fields, close button list.
        # Remove all highlights except for the user-selected job.
        self.clear_job_search_highlights(keep_highlight_job_id=job["id"])

        # Refresh chart visuals
        self.update_tick_locator()
        self.fig.canvas.draw_idle()

    def clear_job_search_highlights(self, keep_highlight_job_id: int = -1):
        """Remove highlights from searched jobs."""
        # Remove 'highlights' from thin bars
        for job_id in self.searched_job_ids:
            # Remove highlights from all searched jobs besides the saved job
            if job_id != keep_highlight_job_id:
                matplotlib.pyplot.setp(
                    self.id_to_bar[str(job_id)], linewidth=0, alpha=0.3
                )
        # If we didn't have any job to save the highlight for, clear the list.
        if keep_highlight_job_id == -1:
            self.searched_job_ids.clear()
        else:
            self.searched_job_ids = [keep_highlight_job_id]
        self.fig.canvas.draw_idle()

    def reset_chart_view(self):
        """Move the chart back to the initial view."""
        self.ax.set_xlim(
            date.today() + timedelta(days=20), date.today() - timedelta(days=2)
        )
        self.ax.invert_xaxis()

        self.ax.set_ylim(self.ylim_start_job, self.ylim_start_job + 15)
        self.ax.invert_yaxis()

        # Also clear any jobs highlighted by search
        self.clear_job_search_highlights()

        self.update_tick_locator()
        self.fig.canvas.draw_idle()

    def on_quit(self):
        """Destroy the main tkinter application and any child windows."""
        logger.info("Exiting program")
        # If the app doesn't close properly, try closing the current chart as well.
        # matplotlib.pyplot.close(self.fig)

        # root.destroy() exits the current window.
        # root.quit() exits the entire tkinter application (includes children))
        self.quit()


if __name__ == "__main__":
    prune_files_in_dir(pathlib.Path("data/logs"), NUM_LOGS)
    logger.info("Starting")
    # Initialize and run the program until the user closes it.
    app = App()
    app.mainloop()
    logger.info("Exited Successfully")
