# Horizon
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![Matplotlib](https://img.shields.io/badge/Matplotlib-%23ffffff.svg?style=for-the-badge&logo=Matplotlib&logoColor=black) ![NumPy](https://img.shields.io/badge/numpy-%23013243.svg?style=for-the-badge&logo=numpy&logoColor=white) ![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)

>"Look to the horizon"

Lightweight workload visualizer
- Modern user interface
- Visualize busy periods with the main window
	- Controls to zoom, pan, and find specific jobs
- Add, modify, and delete jobs (individual tasks)
- Options menu to tweak appearance, job type presets, and logic
- Written in Python
- Multi-platform
	- Windows
	- MacOS
	- Linux

## Example Screenshot:
![Image of Horizon's main graphical user interface.](/images/horizon/full_view.png)

## How To Use

### Downloading/Installation

Download and place the files in `src/` (horizon.py, ctkdatepicker.py) together in a location of your choosing. Note that Horizon will generate additional files/folders to store user data in this location.
#### Install Libraries
Install [Python](https://www.python.org/downloads/) (TAG was developed on Python 3.12)
```bash
pip install numpy
pip install matplotlib
pip install customtkinter
pip install humanize
```
### Start Horizon

#### Option 1: Via command line
```bash
# Move into the directory with Horizon's files
cd path/to/horizon
# Run Horizon
python horizon.py
```

#### Option 2: Run horizon.py with IDLE
If your Python installation included IDLE (Python's intrepreter), you can right click and open horizon.py with IDLE
- If you set IDLE as the default program for .py files, you can simply double-click on horizon.py to open it (as you would with any program/executable)
- You can also create a shortcut to horizon.py. This shortcut can be renamed or moved to a location of your choice (such as the desktop or start menu)
### Main Window: Workload Visualizer
- Displays each day (vertical columns)
	- Can see the jobs that are budgeted to be work on in that day
- Displays each job (horizontal bars)
	- Text indicates the client and job type
	- Thin light blue line: a line from the start to end date of the job, but where work isn't budgeted to take place on this job
	- Thick blue bar: days where the job is budgeted to be actively worked on
	- Thick white bar: A marker that the job has been completed (no further work needs to be budgeted)
- Interactive
	- Pan to see jobs to the left (past) and right (future)
	- Zoom out to see several years worth of data
	- Click on a job to view/modify it (See the "View Job Details" section below)
	- Recenter chart: go to the default view
	- Search Jobs: quickly find jobs matching a given client

![Image of Horizon's main graphical user interface.](/images/horizon/full_view.png)
### View Job Details
This menu is opened when viewing, creating, modifying, and deleting jobs.
- Auto-fill information for repeat clients, by filtering clients as you type
- Price:
	- Revenue gained upon completing the job
	- Used to provide the budgeted effort ("work units") it will take to complete the job.
	- Used for calculating revenue in the Finance tab
- Job Type:
	- Dropdown containing preset types (set to Research in the below screenshot)
	- Displayed on the main window, alongside client name
- Notes
	- Additional notes about this job
- Start/End:
	- The intake and due dates of the job.
	- The end date is used as the basis for when work is budgeted to complete this job.
	- The duration of the job is displayed ("7 days" in the screenshot below)
- Completed:
	- Mark job as completed
- Add/Update/Delete:
	- New jobs can only be added (close the menu to cancel adding the job)
	- Existing jobs can either be updated or deleted.

![Image of Add Job menu.](/images/horizon/add_job.png)

> [!IMPORTANT]
> Horizon will warn users of unusual input:
> - Price couldn't be processed as a number
> - Job starts after the end date (or vice versa)
> - Job has a duration longer than one year
> - Job starts after today
> - Job is due before today (and isn't marked as complete)
### View Finances
- Daily: A per-job, roughly "continuous" line graph
- Monthly: A cumulative per-month chart
- Yearly: A cumulative pet-year chart (shown below)
- Summary: Text summary of revenue, broken down by year and month.

![Image of Finances tab.](/images/horizon/finances.png)

> [!NOTE]
> All amounts are revenue (sales before expenses), based on the work units of the job.

### Set Options
- Change window name and appearance
- Support for light/dark mode
	- If set to "system", will attempt to use the system's current setting.
- Set Job Type presets (used when adding a job)
- Grace Period:
	- How many days a job is budgeted to be completed ahead of it's written due date
	- Helpful to add some leeway for going over budget/lagging behind
- Work Units Per Day:
	- The average amount of work units that your organization fulfills in a single day.
	- Lower this amount if jobs are being completed behind schedule
- Reset to default settings

![Image of Options menu.](/images/horizon/options.png)

## Acknowledgements
- CTKDatePicker:
	- Provided under the MIT license.
	- Original author: maxverwiebe
	- https://github.com/maxverwiebe/CTkDatePicker
	- Modified for use with Horizon's API
---
2026 Oliver Pardi