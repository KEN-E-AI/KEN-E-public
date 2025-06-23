#!/usr/bin/env python3
"""
Kene API CLI Manager

A comprehensive command-line interface for managing Activities, Metrics, Insights, and Intuitions
through the Kene API with confirmation steps and rich console output.
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

console = Console()


class KeneAPIClient:
    """Client for interacting with the Kene API."""
    
    # API endpoints
    ACTIVITIES_ENDPOINT = "/api/v1/activities/"
    METRICS_ENDPOINT = "/api/v1/metrics/"
    INSIGHTS_ENDPOINT = "/api/v1/insights/"
    INTUITIONS_ENDPOINT = "/api/v1/intuitions/"
    # Firestore endpoints
    FIRESTORE_KPI_ENDPOINT = "/api/v1/firestore/kpi-settings"
    FIRESTORE_FUNNEL_STEPS_ENDPOINT = "/api/v1/firestore/funnel-steps"
    FIRESTORE_CHANNELS_ENDPOINT = "/api/v1/firestore/channels"
    FIRESTORE_TACTICS_ENDPOINT = "/api/v1/firestore/tactics"
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the API with error handling."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    console.print(f"[red]Details: {error_detail}[/red]")
                except json.JSONDecodeError:
                    console.print(f"[red]Response: {e.response.text}[/red]")
            raise
    
    # Activities methods
    def get_activities(self, account_id: str) -> Dict[str, Any]:
        """Get all activities for an account."""
        return self._make_request("GET", f"{self.ACTIVITIES_ENDPOINT}?account_id={account_id}")
    
    def create_activity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new activity."""
        return self._make_request("POST", self.ACTIVITIES_ENDPOINT, json=data)
    
    def update_activity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing activity."""
        return self._make_request("PUT", self.ACTIVITIES_ENDPOINT, json=data)
    
    def delete_activity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an activity."""
        return self._make_request("DELETE", self.ACTIVITIES_ENDPOINT, json=data)
    
    # Metrics methods
    def get_metrics(self, account_id: str) -> Dict[str, Any]:
        """Get all metrics for an account."""
        return self._make_request("GET", f"{self.METRICS_ENDPOINT}?account_id={account_id}")
    
    def create_metric(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new metric."""
        return self._make_request("POST", self.METRICS_ENDPOINT, json=data)
    
    def update_metric(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing metric."""
        return self._make_request("PUT", self.METRICS_ENDPOINT, json=data)
    
    def delete_metric(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a metric."""
        return self._make_request("DELETE", self.METRICS_ENDPOINT, json=data)
    
    # Insights methods
    def get_insights(self, account_id: str) -> Dict[str, Any]:
        """Get all insights for an account."""
        return self._make_request("GET", f"{self.INSIGHTS_ENDPOINT}?account_id={account_id}")
    
    def create_insight(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new insight."""
        return self._make_request("POST", self.INSIGHTS_ENDPOINT, json=data)
    
    def update_insight(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing insight."""
        return self._make_request("PUT", self.INSIGHTS_ENDPOINT, json=data)
    
    def delete_insight(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an insight."""
        return self._make_request("DELETE", self.INSIGHTS_ENDPOINT, json=data)
    
    # Intuitions methods
    def get_intuitions(self, account_id: str) -> Dict[str, Any]:
        """Get all intuitions for an account."""
        return self._make_request("GET", f"{self.INTUITIONS_ENDPOINT}?account_id={account_id}")
    
    def create_intuition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new intuition."""
        return self._make_request("POST", self.INTUITIONS_ENDPOINT, json=data)
    
    def update_intuition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing intuition."""
        return self._make_request("PUT", self.INTUITIONS_ENDPOINT, json=data)
    
    def delete_intuition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an intuition."""
        return self._make_request("DELETE", self.INTUITIONS_ENDPOINT, json=data)
    
    # KPI Settings methods
    def get_kpi_setting(self, account_id: str, kpi_name: str) -> Dict[str, Any]:
        """Get a specific KPI setting."""
        return self._make_request("GET", f"{self.FIRESTORE_KPI_ENDPOINT}/{account_id}/{kpi_name}")
    
    def update_kpi_setting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a KPI setting."""
        return self._make_request("PUT", self.FIRESTORE_KPI_ENDPOINT, json=data)
    
    def get_all_kpi_settings(self, account_id: str) -> Dict[str, Any]:
        """Get all KPI settings for an account."""
        return self._make_request("GET", f"{self.FIRESTORE_KPI_ENDPOINT}/{account_id}")
    
    # Funnel Steps methods
    def create_funnel_step(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new funnel step."""
        return self._make_request("POST", self.FIRESTORE_FUNNEL_STEPS_ENDPOINT, json=data)
    
    def get_funnel_steps(self, account_id: str, funnel_type: str, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Get all funnel steps for a funnel."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("GET", f"{self.FIRESTORE_FUNNEL_STEPS_ENDPOINT}/{account_id}/{funnel_type}{params}")
    
    def get_funnel_step(self, account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific funnel step."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("GET", f"{self.FIRESTORE_FUNNEL_STEPS_ENDPOINT}/{account_id}/{funnel_type}/{funnel_step_num}{params}")
    
    def update_funnel_step(self, account_id: str, funnel_type: str, funnel_step_num: int, data: Dict[str, Any], big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Update a funnel step."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("PUT", f"{self.FIRESTORE_FUNNEL_STEPS_ENDPOINT}/{account_id}/{funnel_type}/{funnel_step_num}{params}", json=data)
    
    def delete_funnel_step(self, account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Delete a funnel step."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("DELETE", f"{self.FIRESTORE_FUNNEL_STEPS_ENDPOINT}/{account_id}/{funnel_type}/{funnel_step_num}{params}")
    
    # Channels methods
    def create_channel(self, data: Dict[str, Any], account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new channel."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("POST", f"{self.FIRESTORE_CHANNELS_ENDPOINT}{params}", json=data)
    
    def get_channels(self, account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Get all channels in a funnel step."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("GET", f"{self.FIRESTORE_CHANNELS_ENDPOINT}{params}")
    
    def get_channel(self, channel_name: str, account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific channel."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("GET", f"{self.FIRESTORE_CHANNELS_ENDPOINT}/{channel_name}{params}")
    
    def update_channel(self, channel_name: str, data: Dict[str, Any], account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Update a channel."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("PUT", f"{self.FIRESTORE_CHANNELS_ENDPOINT}/{channel_name}{params}", json=data)
    
    def delete_channel(self, channel_name: str, account_id: str, funnel_type: str, funnel_step_num: int, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Delete a channel."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("DELETE", f"{self.FIRESTORE_CHANNELS_ENDPOINT}/{channel_name}{params}")
    
    # Tactics methods
    def create_tactic(self, data: Dict[str, Any], account_id: str, funnel_type: str, funnel_step_num: int, channel_name: str, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new tactic."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}&channel_name={channel_name}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("POST", f"{self.FIRESTORE_TACTICS_ENDPOINT}{params}", json=data)
    
    def get_tactics(self, account_id: str, funnel_type: str, funnel_step_num: int, channel_name: str, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Get all tactics in a channel."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}&channel_name={channel_name}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("GET", f"{self.FIRESTORE_TACTICS_ENDPOINT}{params}")
    
    def get_tactic(self, tactic_name: str, account_id: str, funnel_type: str, funnel_step_num: int, channel_name: str, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific tactic."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}&channel_name={channel_name}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("GET", f"{self.FIRESTORE_TACTICS_ENDPOINT}/{tactic_name}{params}")
    
    def update_tactic(self, tactic_name: str, data: Dict[str, Any], account_id: str, funnel_type: str, funnel_step_num: int, channel_name: str, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Update a tactic."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}&channel_name={channel_name}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("PUT", f"{self.FIRESTORE_TACTICS_ENDPOINT}/{tactic_name}{params}", json=data)
    
    def delete_tactic(self, tactic_name: str, account_id: str, funnel_type: str, funnel_step_num: int, channel_name: str, big_bet_name: Optional[str] = None) -> Dict[str, Any]:
        """Delete a tactic."""
        params = f"?account_id={account_id}&funnel_type={funnel_type}&funnel_step_num={funnel_step_num}&channel_name={channel_name}"
        if big_bet_name:
            params += f"&big_bet_name={big_bet_name}"
        return self._make_request("DELETE", f"{self.FIRESTORE_TACTICS_ENDPOINT}/{tactic_name}{params}")
    

class KeneCLI:
    """Command Line Interface for Kene API."""
    
    # Constants
    SAVE_CHANGES_PROMPT = "Save changes?"
    CANNOT_UNDONE_WARNING = "[red]This action cannot be undone![/red]"
    CHOOSE_OPTION_PROMPT = "Choose an option"
    ENTER_ACTIVITY_NUMBER = "Enter activity number"
    ENTER_METRIC_NUMBER = "Enter metric number"
    ENTER_LOG_NUMBER = "Enter log number"
    DIRECTION_OF_INFLUENCE = "Direction of influence"
    NO_ACTIVITIES_FOUND = "[yellow]No activities found. Create activities first.[/yellow]"
    ACTIVITIES_LOGS_ENDPOINT = "/api/v1/activities/logs"
    
    def __init__(self):
        self.client = KeneAPIClient()
        self.account_id = "a000001"
    
    def run(self):
        """Main CLI loop."""
        console.print(Panel.fit(
            "[bold blue]Kene API Command Line Interface[/bold blue]\n"
            "Manage activities, metrics, insights, and intuitions",
            title="Welcome"
        ))
        
        # Get account ID
        self.account_id = Prompt.ask(
            "Enter account ID", 
            default="a000001"
        )
        
        while True:
            try:
                choice = self._show_main_menu()
                if choice == "1":
                    self._manage_activities()
                elif choice == "2":
                    self._manage_metrics()
                elif choice == "3":
                    self._manage_insights()
                elif choice == "4":
                    self._manage_intuitions()
                elif choice == "5":
                    self._manage_kpi_settings()
                elif choice == "6":
                    self._manage_funnel_steps()
                elif choice == "7":
                    self._manage_channels()
                elif choice == "8":
                    self._manage_tactics()
                elif choice == "9":
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                else:
                    console.print("[red]Invalid choice. Please try again.[/red]")
            except KeyboardInterrupt:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]An error occurred: {e}[/red]")
    
    def _show_main_menu(self) -> str:
        """Display the main menu and get user choice."""
        console.print("\n" + "="*50)
        console.print(f"[bold]Account ID:[/bold] {self.account_id}")
        console.print("\n[bold]Main Menu:[/bold]")
        console.print("1. Manage Activities")
        console.print("2. Manage Metrics")
        console.print("3. Manage Insights")
        console.print("4. Manage Intuitions")
        console.print("5. Manage KPI Settings")
        console.print("6. Manage Funnel Steps")
        console.print("7. Manage Channels")
        console.print("8. Manage Tactics")
        console.print("9. Exit")
        
        return Prompt.ask(self.CHOOSE_OPTION_PROMPT, choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"])
    
    def _show_crud_menu(self, entity_type: str) -> str:
        """Display CRUD menu for an entity type."""
        console.print(f"\n[bold]{entity_type} Management:[/bold]")
        console.print("1. View All")
        console.print("2. Add New")
        console.print("3. Edit Existing")
        console.print("4. Delete")
        console.print("5. Back to Main Menu")
        
        return Prompt.ask(self.CHOOSE_OPTION_PROMPT, choices=["1", "2", "3", "4", "5"])
    
    # Activities Management
    def _manage_activities(self):
        """Manage activities and activity logs."""
        while True:
            choice = self._show_activities_menu()
            if choice == "1":
                self._view_activities()
            elif choice == "2":
                self._add_activity()
            elif choice == "3":
                self._edit_activity()
            elif choice == "4":
                self._delete_activity()
            elif choice == "5":
                self._manage_activity_logs()
            elif choice == "6":
                break
    
    def _show_activities_menu(self) -> str:
        """Display activities management menu."""
        console.print("\n[bold]Activities Management:[/bold]")
        console.print("1. View All Activities")
        console.print("2. Add New Activity")
        console.print("3. Edit Existing Activity")
        console.print("4. Delete Activity")
        console.print("5. Manage Activity Logs")
        console.print("6. Back to Main Menu")
        
        return Prompt.ask(self.CHOOSE_OPTION_PROMPT, choices=["1", "2", "3", "4", "5", "6"])
    
    def _view_activities(self):
        """Display all activities with all relevant fields."""
        response = self.client.get_activities(self.account_id)
        activities = response.get("activities", [])
        
        if not activities:
            console.print("[yellow]No activities found.[/yellow]")
            return
        
        table = Table(title="Activities")
        table.add_column("ID", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Expected Impact", style="yellow")
        table.add_column("Internal", style="blue")
        table.add_column("Known Activity", style="magenta")
        table.add_column("Logs Count", style="red")
        
        for activity in activities:
            description = activity.get("activity_description", "N/A")
            expected_impact = activity.get("expected_impact", "N/A")
            logs_count = len(activity.get("logs", []))
            
            # Truncate long descriptions
            if len(description) > 50:
                description = description[:50] + "..."
            if len(expected_impact) > 30:
                expected_impact = expected_impact[:30] + "..."
                
            table.add_row(
                str(activity.get("id", "N/A")),
                description,
                expected_impact,
                str(activity.get("internal", False)),
                str(activity.get("known_activity", False)),
                str(logs_count)
            )
        
        console.print(table)
    
    def _add_activity(self):
        """Add a new activity with all fields from ActivityRequest."""
        console.print("\n[bold]Add New Activity[/bold]")
        
        # Required field
        activity_description = Prompt.ask("Activity description (required)")
        
        # Optional fields
        expected_impact = Prompt.ask("Expected impact", default="")
        internal = Confirm.ask("Is this an internal activity?", default=False)
        known_activity = Confirm.ask("Is this a known activity?", default=False)
        
        # Validation
        if not activity_description.strip():
            console.print("[red]Activity description is required![/red]")
            return
        
        data = {
            "account_id": self.account_id,
            "activity_description": activity_description,
            "expected_impact": expected_impact,
            "internal": internal,
            "known_activity": known_activity
        }
        
        # Show preview
        self._show_data_preview("Activity", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.create_activity(data)
                console.print("[green]Activity created successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to create activity: {e}[/red]")
    
    def _edit_activity(self):
        """Edit an existing activity."""
        response = self.client.get_activities(self.account_id)
        activities = response.get("activities", [])
        
        if not activities:
            console.print("[yellow]No activities found to edit.[/yellow]")
            return
        
        # Select activity to edit
        console.print("\n[bold]Select Activity to Edit:[/bold]")
        for i, activity in enumerate(activities, 1):
            description = activity.get("activity_description", "N/A")
            if len(description) > 50:
                description = description[:50] + "..."
            console.print(f"{i}. {description}")
        
        choice = Prompt.ask(
            self.ENTER_ACTIVITY_NUMBER,
            choices=[str(i) for i in range(1, len(activities) + 1)]
        )
        
        activity = activities[int(choice) - 1]
        activity_id = activity.get("id")
        
        # Edit fields
        console.print(f"\n[bold]Editing Activity (ID: {activity_id})[/bold]")
        data = {
            "account_id": self.account_id,
            "id": activity_id,
            "activity_description": Prompt.ask(
                "Activity description", 
                default=activity.get("activity_description", "")
            ),
            "expected_impact": Prompt.ask(
                "Expected impact", 
                default=activity.get("expected_impact", "")
            ),
            "internal": Confirm.ask(
                "Is this an internal activity?", 
                default=activity.get("internal", False)
            ),
            "known_activity": Confirm.ask(
                "Is this a known activity?", 
                default=activity.get("known_activity", False)
            )
        }
        
        # Validation
        if not data["activity_description"].strip():
            console.print("[red]Activity description is required![/red]")
            return
        
        self._show_data_preview("Updated Activity", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.update_activity(data)
                console.print("[green]Activity updated successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to update activity: {e}[/red]")
    
    def _delete_activity(self):
        """Delete an activity."""
        response = self.client.get_activities(self.account_id)
        activities = response.get("activities", [])
        
        if not activities:
            console.print("[yellow]No activities found to delete.[/yellow]")
            return
        
        # Select activity to delete
        console.print("\n[bold]Select Activity to Delete:[/bold]")
        for i, activity in enumerate(activities, 1):
            description = activity.get("activity_description", "N/A")
            if len(description) > 50:
                description = description[:50] + "..."
            console.print(f"{i}. {description}")
        
        choice = Prompt.ask(
            self.ENTER_ACTIVITY_NUMBER,
            choices=[str(i) for i in range(1, len(activities) + 1)]
        )
        
        activity = activities[int(choice) - 1]
        activity_id = activity.get("id")
        
        current_desc = activity.get('activity_description', 'N/A')
        console.print(f"\n[bold red]DELETE Activity: {current_desc}[/bold red]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        if Confirm.ask("Are you sure you want to delete this activity?"):
            data = {
                "account_id": self.account_id,
                "id": activity_id
            }
            
            try:
                self.client.delete_activity(data)
                console.print("[green]Activity deleted successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to delete activity: {e}[/red]")
    
    # Activity Logs Management
    def _manage_activity_logs(self):
        """Manage activity logs."""
        while True:
            choice = self._show_crud_menu("Activity Logs")
            if choice == "1":
                self._view_activity_logs()
            elif choice == "2":
                self._add_activity_log()
            elif choice == "3":
                self._edit_activity_log()
            elif choice == "4":
                self._delete_activity_log()
            elif choice == "5":
                break
    
    def _view_activity_logs(self):
        """Display all activity logs for activities."""
        response = self.client.get_activities(self.account_id)
        activities = response.get("activities", [])
        
        if not activities:
            console.print("[yellow]No activities found.[/yellow]")
            return
        
        # Collect all logs from all activities
        all_logs = []
        for activity in activities:
            logs = activity.get("logs", [])
            for log in logs:
                log["parent_activity_description"] = activity.get("activity_description", "N/A")
                all_logs.append(log)
        
        if not all_logs:
            console.print("[yellow]No activity logs found.[/yellow]")
            return
        
        table = Table(title="Activity Logs")
        table.add_column("Log ID", style="cyan")
        table.add_column("Activity", style="green")
        table.add_column("Start Date", style="yellow")
        table.add_column("End Date", style="blue")
        table.add_column("Description", style="magenta")
        
        for log in all_logs:
            activity_desc = log.get("parent_activity_description", "N/A")
            if len(activity_desc) > 30:
                activity_desc = activity_desc[:30] + "..."
            
            log_desc = log.get("description", "N/A")
            if len(log_desc) > 40:
                log_desc = log_desc[:40] + "..."
                
            table.add_row(
                str(log.get("id", "N/A")),
                activity_desc,
                log.get("start_date", "N/A"),
                log.get("end_date", "N/A"),
                log_desc
            )
        
        console.print(table)
    
    def _add_activity_log(self):
        """Add a new activity log with all fields from ActivityLogRequest."""
        console.print("\n[bold]Add New Activity Log[/bold]")
        
        # First select an activity
        activities_response = self.client.get_activities(self.account_id)
        activities = activities_response.get("activities", [])
        
        if not activities:
            console.print(self.NO_ACTIVITIES_FOUND)
            return
        
        console.print("\n[bold]Select Activity for Log:[/bold]")
        for i, activity in enumerate(activities, 1):
            desc = activity.get("activity_description", "N/A")
            if len(desc) > 50:
                desc = desc[:50] + "..."
            console.print(f"{i}. {desc}")
        
        choice = Prompt.ask(
            self.ENTER_ACTIVITY_NUMBER,
            choices=[str(i) for i in range(1, len(activities) + 1)]
        )
        
        selected_activity = activities[int(choice) - 1]
        activity_id = selected_activity.get("id")
        
        # Get log fields
        start_date = Prompt.ask("Start date (YYYY-MM-DD)")
        end_date = Prompt.ask("End date (YYYY-MM-DD)", default=start_date)
        description = Prompt.ask("Description", default="")
        
        data = {
            "account_id": self.account_id,
            "activity_id": activity_id,
            "start_date": start_date,
            "end_date": end_date,
            "description": description
        }
        
        # Show preview
        self._show_data_preview("Activity Log", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                # Use the activities endpoint for logs
                self.client._make_request("POST", self.ACTIVITIES_LOGS_ENDPOINT, json=data)
                console.print("[green]Activity log created successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to create activity log: {e}[/red]")
    
    def _edit_activity_log(self):
        """Edit an existing activity log."""
        # Get all activity logs
        response = self.client.get_activities(self.account_id)
        activities = response.get("activities", [])
        
        all_logs = []
        for activity in activities:
            logs = activity.get("logs", [])
            for log in logs:
                log["parent_activity_description"] = activity.get("activity_description", "N/A")
                all_logs.append(log)
        
        if not all_logs:
            console.print("[yellow]No activity logs found to edit.[/yellow]")
            return
        
        # Select log to edit
        console.print("\n[bold]Select Activity Log to Edit:[/bold]")
        for i, log in enumerate(all_logs, 1):
            activity_desc = log.get("parent_activity_description", "N/A")
            log_desc = log.get("description", "N/A")
            console.print(f"{i}. {activity_desc} - {log_desc}")
        
        choice = Prompt.ask(
            self.ENTER_LOG_NUMBER,
            choices=[str(i) for i in range(1, len(all_logs) + 1)]
        )
        
        selected_log = all_logs[int(choice) - 1]
        log_id = selected_log.get("id")
        
        # Edit fields
        console.print(f"\n[bold]Editing Activity Log (ID: {log_id})[/bold]")
        
        start_date = Prompt.ask("Start date (YYYY-MM-DD)", default=selected_log.get("start_date", ""))
        end_date = Prompt.ask("End date (YYYY-MM-DD)", default=selected_log.get("end_date", ""))
        description = Prompt.ask("Description", default=selected_log.get("description", ""))
        
        data = {
            "account_id": self.account_id,
            "id": log_id,
            "start_date": start_date,
            "end_date": end_date,
            "description": description
        }
        
        self._show_data_preview("Updated Activity Log", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                # Use the activities endpoint for logs
                self.client._make_request("PUT", self.ACTIVITIES_LOGS_ENDPOINT, json=data)
                console.print("[green]Activity log updated successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to update activity log: {e}[/red]")
    
    def _delete_activity_log(self):
        """Delete an activity log."""
        # Get all activity logs
        response = self.client.get_activities(self.account_id)
        activities = response.get("activities", [])
        
        all_logs = []
        for activity in activities:
            logs = activity.get("logs", [])
            for log in logs:
                log["parent_activity_description"] = activity.get("activity_description", "N/A")
                all_logs.append(log)
        
        if not all_logs:
            console.print("[yellow]No activity logs found to delete.[/yellow]")
            return
        
        # Select log to delete
        console.print("\n[bold]Select Activity Log to Delete:[/bold]")
        for i, log in enumerate(all_logs, 1):
            activity_desc = log.get("parent_activity_description", "N/A")
            log_desc = log.get("description", "N/A")
            console.print(f"{i}. {activity_desc} - {log_desc}")
        
        choice = Prompt.ask(
            self.ENTER_LOG_NUMBER,
            choices=[str(i) for i in range(1, len(all_logs) + 1)]
        )
        
        selected_log = all_logs[int(choice) - 1]
        log_id = selected_log.get("id")
        
        console.print(f"\n[bold red]DELETE Activity Log: {selected_log.get('description', 'N/A')}[/bold red]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        if Confirm.ask("Are you sure you want to delete this activity log?"):
            data = {
                "account_id": self.account_id,
                "id": log_id
            }
            
            try:
                # Use the activities endpoint for logs
                self.client._make_request("DELETE", self.ACTIVITIES_LOGS_ENDPOINT, json=data)
                console.print("[green]Activity log deleted successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to delete activity log: {e}[/red]")
    
    # Metrics Management
    def _manage_metrics(self):
        """Manage metrics."""
        while True:
            choice = self._show_crud_menu("Metrics")
            if choice == "1":
                self._view_metrics()
            elif choice == "2":
                self._add_metric()
            elif choice == "3":
                self._edit_metric()
            elif choice == "4":
                self._delete_metric()
            elif choice == "5":
                break
    
    def _view_metrics(self):
        """Display all metrics with all relevant fields."""
        response = self.client.get_metrics(self.account_id)
        metrics = response.get("metrics", [])
        
        if not metrics:
            console.print("[yellow]No metrics found.[/yellow]")
            return
        
        table = Table(title="Metrics")
        table.add_column("ID", style="cyan")
        table.add_column("Verbose Name", style="green") 
        table.add_column("Metric Name", style="yellow")
        table.add_column("Description", style="blue")
        table.add_column("Expression", style="magenta")
        table.add_column("D3 Format", style="red")
        table.add_column("Components", style="white")
        table.add_column("Dataset ID", style="cyan")
        table.add_column("Dataset Name", style="green")
        table.add_column("Dataset Products", style="yellow")
        
        for metric in metrics:
            # Extract and format metric data for display
            metric_data = self._extract_metric_display_data(metric)
            
            table.add_row(
                metric_data["id"],
                metric_data["verbose_name"],
                metric_data["metric_name"],
                metric_data["description"],
                metric_data["expression"],
                metric_data["d3_format"],
                metric_data["components"],
                metric_data["dataset_id"],
                metric_data["dataset_name"],
                metric_data["dataset_products"]
            )
        
        console.print(table)
    
    def _extract_metric_display_data(self, metric):
        """Extract and format metric data for table display."""
        data = {
            "id": str(metric.get("id", "N/A")),
            "verbose_name": metric.get("verbose_name", "N/A"),
            "metric_name": metric.get("metric_name", "N/A"),
            "description": metric.get("description", "N/A"),
            "expression": metric.get("expression", "N/A"),
            "d3_format": metric.get("d3_format", "N/A"),
            "components": str(metric.get("account_components", [])),
            "dataset_id": str(metric.get("related_dataset_id", "N/A")),
            "dataset_name": metric.get("related_dataset_name", "N/A"),
            "dataset_products": str(metric.get("related_dataset_products", []))
        }
        
        # Truncate long values for display
        truncation_limits = {
            "verbose_name": 25,
            "metric_name": 20,
            "description": 30,
            "expression": 35,
            "components": 25,
            "dataset_name": 20,
            "dataset_products": 25
        }
        
        for field, limit in truncation_limits.items():
            if len(data[field]) > limit:
                data[field] = data[field][:limit] + "..."
        
        return data
    
    def _add_metric(self):
        """Add a new metric with all fields from MetricRequest."""
        console.print("\n[bold]Add New Metric[/bold]")
        
        # Required fields
        verbose_name = Prompt.ask("Verbose name (human-friendly name, required)")
        metric_name = Prompt.ask("Metric name (snake_case, required)", default=verbose_name.lower().replace(" ", "_"))
        
        # Optional fields
        description = Prompt.ask("Description", default="")
        expression = Prompt.ask("SQL expression", default="")
        d3_format = Prompt.ask("D3 format (e.g., '.2f', ',d')", default="")
        
        # Account components as comma-separated list
        components_str = Prompt.ask("Account components (comma-separated)", default="")
        account_components = [comp.strip() for comp in components_str.split(",") if comp.strip()] if components_str else []
        
        # Related dataset ID (required for linking)
        dataset_id_str = Prompt.ask("Related dataset ID (required)")
        
        # Validate dataset ID
        if not dataset_id_str.isdigit():
            console.print("[red]Dataset ID must be a valid number![/red]")
            return
        
        related_dataset_id = int(dataset_id_str)
        
        # Validation
        if not verbose_name.strip():
            console.print("[red]Verbose name is required![/red]")
            return
        if not metric_name.strip():
            console.print("[red]Metric name is required![/red]")
            return
        
        data = {
            "account_id": self.account_id,
            "verbose_name": verbose_name,
            "metric_name": metric_name,
            "description": description,
            "expression": expression,
            "d3_format": d3_format,
            "account_components": account_components,
            "related_dataset_id": related_dataset_id
        }
        
        # Show preview
        self._show_data_preview("Metric", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.create_metric(data)
                console.print("[green]Metric created successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to create metric: {e}[/red]")
    
    def _edit_metric(self):
        """Edit an existing metric with all fields from MetricRequest."""
        response = self.client.get_metrics(self.account_id)
        metrics = response.get("metrics", [])
        
        if not metrics:
            console.print("[yellow]No metrics found to edit.[/yellow]")
            return
        
        # Select metric to edit
        console.print("\n[bold]Select Metric to Edit:[/bold]")
        for i, metric in enumerate(metrics, 1):
            name = metric.get("verbose_name", metric.get("metric_name", "N/A"))
            if len(name) > 50:
                name = name[:50] + "..."
            console.print(f"{i}. {name} (ID: {metric.get('id', 'N/A')})")
        
        choice = Prompt.ask(
            self.ENTER_METRIC_NUMBER,
            choices=[str(i) for i in range(1, len(metrics) + 1)]
        )
        
        metric = metrics[int(choice) - 1]
        metric_id = metric.get("id")
        
        if not metric_id:
            console.print("[red]Selected metric has no valid ID.[/red]")
            return
        
        console.print(f"\n[bold]Editing Metric: {metric.get('verbose_name', 'N/A')}[/bold]")
        
        # Get all field values
        data = self._get_metric_field_values(metric, metric_id)
        
        # Validation
        if not data["verbose_name"].strip():
            console.print("[red]Verbose name is required![/red]")
            return
        if not data["metric_name"].strip():
            console.print("[red]Metric name is required![/red]")
            return
        
        self._show_data_preview("Updated Metric", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.update_metric(data)
                console.print("[green]Metric updated successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to update metric: {e}[/red]")
    
    def _get_metric_field_values(self, metric, metric_id):
        """Get metric field values from user input."""
        # Edit all fields with current values as defaults
        verbose_name = Prompt.ask("Verbose name", default=metric.get("verbose_name", ""))
        metric_name = Prompt.ask("Metric name", default=metric.get("metric_name", ""))
        description = Prompt.ask("Description", default=metric.get("description", ""))
        expression = Prompt.ask("SQL expression", default=metric.get("expression", ""))
        d3_format = Prompt.ask("D3 format", default=metric.get("d3_format", ""))
        
        # Handle account components
        current_components = metric.get("account_components", [])
        components_str = Prompt.ask("Account components (comma-separated)", 
                                  default=", ".join(current_components) if current_components else "")
        account_components = [comp.strip() for comp in components_str.split(",") if comp.strip()] if components_str else []
        
        # Handle related dataset ID
        current_dataset_id = metric.get("related_dataset_id")
        dataset_id_str = Prompt.ask("Related dataset ID", 
                                  default=str(current_dataset_id) if current_dataset_id else "")
        related_dataset_id = int(dataset_id_str) if dataset_id_str.isdigit() else None
        
        return {
            "account_id": self.account_id,
            "id": metric_id,
            "verbose_name": verbose_name,
            "metric_name": metric_name,
            "description": description,
            "expression": expression,
            "d3_format": d3_format,
            "account_components": account_components,
            "related_dataset_id": related_dataset_id
        }
    
    def _delete_metric(self):
        """Delete a metric."""
        response = self.client.get_metrics(self.account_id)
        metrics = response.get("metrics", [])
        
        if not metrics:
            console.print("[yellow]No metrics found to delete.[/yellow]")
            return
        
        # Select metric to delete
        console.print("\n[bold]Select Metric to Delete:[/bold]")
        for i, metric in enumerate(metrics, 1):
            name = metric.get("metric_name", "N/A")
            value = metric.get("metric_value", "N/A")
            console.print(f"{i}. {name}: {value}")
        
        choice = Prompt.ask(
            self.ENTER_METRIC_NUMBER,
            choices=[str(i) for i in range(1, len(metrics) + 1)]
        )
        
        metric = metrics[int(choice) - 1]
        metric_id = metric.get("id")
        
        current_name = metric.get('metric_name', 'N/A')
        console.print(f"\n[bold red]DELETE Metric: {current_name}[/bold red]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        if Confirm.ask("Are you sure you want to delete this metric?"):
            data = {
                "account_id": self.account_id,
                "id": metric_id
            }
            
            try:
                self.client.delete_metric(data)
                console.print("[green]Metric deleted successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to delete metric: {e}[/red]")
    
    # Insights Management
    def _manage_insights(self):
        """Manage insights."""
        while True:
            choice = self._show_crud_menu("Insights")
            if choice == "1":
                self._view_insights()
            elif choice == "2":
                self._add_insight()
            elif choice == "3":
                self._edit_insight()
            elif choice == "4":
                self._delete_insight()
            elif choice == "5":
                break
    
    def _view_insights(self):
        """Display all insights."""
        response = self.client.get_insights(self.account_id)
        insights = response.get("insights", [])
        
        if not insights:
            console.print("[yellow]No insights found.[/yellow]")
            return
        
        self._display_insights_table(insights)
    
    def _view_intuitions(self):
        """Display all intuitions."""
        response = self.client.get_insights(self.account_id)
        intuitions = response.get("intuitions", [])
        
        if not intuitions:
            console.print("[yellow]No intuitions found.[/yellow]")
            return
        
        self._display_intuitions_table(intuitions)
    
    def _display_insights_table(self, insights):
        """Display insights in a table format."""
        if not insights:
            return
            
        console.print("\n[bold]Insights (ActivityLog → Metric relationships):[/bold]")
        table = Table(title="Insights")
        table.add_column("Activity ID", style="cyan")
        table.add_column("Activity Log ID", style="blue")
        table.add_column("Metric", style="green")
        table.add_column("Direction", style="yellow")
        table.add_column("Relationship", style="magenta")
        table.add_column("Evidence", style="white")
        
        for insight in insights:
            activity_id = self._truncate_string(insight.get("activity_id", "N/A"), 15)
            activity_log_id = self._truncate_string(insight.get("activity_log_id", "N/A"), 15)
            metric_name = self._truncate_string(insight.get("metric_verbose_name", "N/A"), 25)
            direction = str(insight.get("direction", "N/A"))
            relationship = str(insight.get("relationship_type", "N/A"))
            
            # Format evidence for display
            evidence_summary = self._format_evidence_summary(insight.get("evidence"))
                
            table.add_row(activity_id, activity_log_id, metric_name, direction, relationship, evidence_summary)
        
        console.print(table)
    
    def _display_intuitions_table(self, intuitions):
        """Display intuitions in a table format."""
        if not intuitions:
            return
            
        console.print("\n[bold]Intuitions (Activity → Metric relationships):[/bold]")
        table = Table(title="Intuitions")
        table.add_column("Activity ID", style="cyan")
        table.add_column("Metric ID", style="green")
        table.add_column("Direction", style="yellow")
        
        for intuition in intuitions:
            activity_id = self._truncate_string(intuition.get("activity_id", "N/A"), 20)
            metric_id = self._truncate_string(intuition.get("metric_id", "N/A"), 20)
            direction = str(intuition.get("direction", "N/A"))
                
            table.add_row(activity_id, metric_id, direction)
        
        console.print(table)
    
    def _truncate_string(self, text, max_length):
        """Truncate string if it exceeds max_length."""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    def _format_evidence_summary(self, evidence):
        """Format evidence data for table display."""
        if not evidence:
            return "None"
        
        try:
            # Extract key information from evidence
            active_conf = "N/A"
            influence_likely = "N/A"
            
            if isinstance(evidence, dict):
                if "active_evidence" in evidence:
                    active_conf = evidence["active_evidence"].get("active_confidence", "N/A")
                if "influence_evidence" in evidence:
                    influence_likely = str(evidence["influence_evidence"].get("influence_likely", "N/A"))
            elif hasattr(evidence, 'active_evidence') and hasattr(evidence, 'influence_evidence'):
                if evidence.active_evidence:
                    active_conf = evidence.active_evidence.active_confidence
                if evidence.influence_evidence:
                    influence_likely = str(evidence.influence_evidence.influence_likely)
            
            # Create compact summary
            summary = f"Conf:{active_conf}, Likely:{influence_likely}"
            return self._truncate_string(summary, 20)
        except Exception:
            return "Error"
    
    def _add_insight(self):
        """Add a new insight (ActivityLog → Metric relationship)."""
        console.print("\n[bold]Add New Insight[/bold]")
        console.print("Insights link ActivityLog entries to Metrics, showing confirmed influence.")
        
        # Get available activity logs and metrics
        if not self._check_required_entities_for_insight():
            return
            
        activity_log_id = self._select_activity_log()
        if not activity_log_id:
            return
            
        metric_id = self._select_metric()
        if not metric_id:
            return
        
        # Get relationship type first
        relationship_type = Prompt.ask(
            "Relationship type",
            choices=["INFLUENCE_CONFIRMED", "NO_INFLUENCE_CONFIRMED"],
            default="INFLUENCE_CONFIRMED"
        )
        
        # Get direction only if influence is confirmed
        direction = None
        if relationship_type == "INFLUENCE_CONFIRMED":
            direction = Prompt.ask(
                self.DIRECTION_OF_INFLUENCE,
                choices=["positive", "negative"],
                default="positive"
            )
        
        # Create evidence data
        evidence_data = self._create_evidence_data(relationship_type)
        
        data = {
            "account_id": self.account_id,
            "activity_log_id": activity_log_id,
            "metric_id": metric_id,
            "relationship_type": relationship_type,
            "direction": direction,
            "evidence": evidence_data
        }
        
        # Show preview
        self._show_data_preview("Insight", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.create_insight(data)
                console.print("[green]Insight created successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to create insight: {e}[/red]")
    
    def _check_required_entities_for_insight(self):
        """Check if required entities exist for creating insights."""
        # Check for activity logs
        activities_response = self.client.get_activities(self.account_id)
        activities = activities_response.get("activities", [])
        
        if not activities:
            console.print("[yellow]No activities found. Create activities first.[/yellow]")
            return False
        
        # Check for metrics
        metrics_response = self.client.get_metrics(self.account_id)
        metrics = metrics_response.get("metrics", [])
        
        if not metrics:
            console.print("[yellow]No metrics found. Create metrics first.[/yellow]")
            return False
            
        return True
    
    def _select_activity_log(self):
        """Select an activity log for insight creation."""
        activities_response = self.client.get_activities(self.account_id)
        activities = activities_response.get("activities", [])
        
        if not activities:
            return None
        
        console.print("\n[bold]Select Activity (with logs):[/bold]")
        activity_choices = dict()
        i = 1
        for activity in activities:
            activity_logs = activity.get("logs", [])
            if activity_logs:
                activity_desc = activity.get("activity_description", "N/A")
                if len(activity_desc) > 40:
                    activity_desc = activity_desc[:40] + "..."
                console.print(f"{i}. {activity_desc} ({len(activity_logs)} logs)")
                activity_choices[str(i)] = activity
                i += 1
        
        if not activity_choices:
            console.print("[yellow]No activities with logs found.[/yellow]")
            return None
        
        choice = Prompt.ask(
            self.ENTER_ACTIVITY_NUMBER,
            choices=list(activity_choices.keys())
        )
        
        selected_activity = activity_choices[choice]
        activity_logs = selected_activity.get("logs", [])
        
        # Select specific activity log
        console.print("\n[bold]Select Activity Log:[/bold]")
        for i, log in enumerate(activity_logs, 1):
            log_id = log.get("id", "N/A")
            console.print(f"{i}. {log_id}")
        
        log_choice = Prompt.ask(
            "Enter log number",
            choices=[str(i) for i in range(1, len(activity_logs) + 1)]
        )
        
        selected_log = activity_logs[int(log_choice) - 1]
        return selected_log.get("id")
    
    def _select_metric(self):
        """Select a metric for insight/intuition creation."""
        metrics_response = self.client.get_metrics(self.account_id)
        metrics = metrics_response.get("metrics", [])
        
        if not metrics:
            return None
        
        console.print("\n[bold]Select Metric:[/bold]")
        for i, metric in enumerate(metrics, 1):
            name = metric.get("verbose_name", metric.get("metric_name", "N/A"))
            if len(name) > 40:
                name = name[:40] + "..."
            console.print(f"{i}. {name}")
        
        choice = Prompt.ask(
            self.ENTER_METRIC_NUMBER,
            choices=[str(i) for i in range(1, len(metrics) + 1)]
        )
        
        selected_metric = metrics[int(choice) - 1]
        return selected_metric.get("id")
    
    def _create_evidence_data(self, relationship_type="INFLUENCE_CONFIRMED"):
        """Create evidence data for insight."""
        console.print("\n[bold]Evidence Configuration:[/bold]")
        
        # Active evidence
        active_confidence = Prompt.ask(
            "Active confidence level",
            choices=["HIGH", "MEDIUM", "LOW"],
            default="MEDIUM"
        )
        
        evidence_description = Prompt.ask(
            "Evidence description (optional)",
            default=""
        )
        
        evidence_list = []
        if evidence_description.strip():
            evidence_list = [evidence_description.strip()]
        
        # Influence evidence - set influence_likely based on relationship type
        influence_likely = relationship_type == "INFLUENCE_CONFIRMED"
        
        # Only ask for alignment if influence is confirmed
        influence_aligned = True  # Default
        if relationship_type == "INFLUENCE_CONFIRMED":
            influence_aligned = Confirm.ask(
                "Is the influence direction aligned with expectations?",
                default=True
            )
        
        return {
            "active_evidence": {
                "active_confidence": active_confidence,
                "evidence": evidence_list,
                "data": None
            },
            "influence_evidence": {
                "influence_direction_aligned": influence_aligned,
                "influence_likely": influence_likely,
                "other_conflicting_insights": [],
                "other_supporting_insights": [],
                "overlapping_conflicting_insights": [],
                "overlapping_supporting_insights": []
            }
        }
    
    def _edit_insight(self):
        """Edit an existing insight (ActivityLog → Metric relationship)."""
        response = self.client.get_insights(self.account_id)
        insights = response.get("insights", [])
        
        if not insights:
            console.print("[yellow]No insights found to edit.[/yellow]")
            return
        
        # Select insight to edit
        console.print("\n[bold]Select Insight to Edit:[/bold]")
        for i, insight in enumerate(insights, 1):
            activity_log_id = insight.get("activity_log_id", "N/A")
            metric_name = insight.get("metric_verbose_name", "N/A")
            direction = insight.get("direction", "N/A")
            console.print(f"{i}. {activity_log_id} → {metric_name} ({direction})")
        
        choice = Prompt.ask(
            "Enter insight number",
            choices=[str(i) for i in range(1, len(insights) + 1)]
        )
        
        insight = insights[int(choice) - 1]
        activity_log_id = insight.get("activity_log_id")
        metric_id = insight.get("metric_id")
        
        # Edit relationship type
        current_relationship = insight.get("relationship_type", "INFLUENCE_CONFIRMED")
        relationship_type = Prompt.ask(
            "Relationship type",
            choices=["INFLUENCE_CONFIRMED", "NO_INFLUENCE_CONFIRMED"],
            default=current_relationship
        )
        
        # Edit direction only if influence is confirmed
        direction = None
        if relationship_type == "INFLUENCE_CONFIRMED":
            current_direction = insight.get("direction", "positive")
            direction = Prompt.ask(
                self.DIRECTION_OF_INFLUENCE,
                choices=["positive", "negative"],
                default=current_direction if current_direction else "positive"
            )
        
        # Create evidence data
        evidence_data = self._create_evidence_data(relationship_type)
        
        data = {
            "account_id": self.account_id,
            "activity_log_id": activity_log_id,
            "metric_id": metric_id,
            "relationship_type": relationship_type,
            "direction": direction,
            "evidence": evidence_data
        }
        
        self._show_data_preview("Updated Insight", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.update_insight(data)
                console.print("[green]Insight updated successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to update insight: {e}[/red]")
    
    def _delete_insight(self):
        """Delete an insight (ActivityLog → Metric relationship)."""
        response = self.client.get_insights(self.account_id)
        insights = response.get("insights", [])
        
        if not insights:
            console.print("[yellow]No insights found to delete.[/yellow]")
            return
        
        # Select insight to delete
        console.print("\n[bold]Select Insight to Delete:[/bold]")
        for i, insight in enumerate(insights, 1):
            activity_log_id = insight.get("activity_log_id", "N/A")
            metric_name = insight.get("metric_verbose_name", "N/A")
            direction = insight.get("direction", "N/A")
            console.print(f"{i}. {activity_log_id} → {metric_name} ({direction})")
        
        choice = Prompt.ask(
            "Enter insight number",
            choices=[str(i) for i in range(1, len(insights) + 1)]
        )
        
        insight = insights[int(choice) - 1]
        activity_log_id = insight.get("activity_log_id")
        metric_id = insight.get("metric_id")
        metric_name = insight.get("metric_verbose_name", "N/A")
        
        console.print(f"\n[bold red]DELETE Insight: {activity_log_id} → {metric_name}[/bold red]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        if Confirm.ask("Are you sure you want to delete this insight?"):
            data = {
                "account_id": self.account_id,
                "activity_log_id": activity_log_id,
                "metric_id": metric_id
            }
            
            try:
                self.client.delete_insight(data)
                console.print("[green]Insight deleted successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to delete insight: {e}[/red]")
    
    # Intuitions Management
    def _manage_intuitions(self):
        """Manage intuitions."""
        while True:
            choice = self._show_crud_menu("Intuitions")
            if choice == "1":
                self._view_intuitions()
            elif choice == "2":
                self._add_intuition()
            elif choice == "3":
                self._edit_intuition()
            elif choice == "4":
                self._delete_intuition()
            elif choice == "5":
                break
    
    def _add_intuition(self):
        """Add a new intuition (Activity → Metric relationship)."""
        console.print("\n[bold]Add New Intuition[/bold]")
        console.print("Intuitions link Activities directly to Metrics, showing likely influence.")
        
        # Check if required entities exist
        if not self._check_required_entities_for_intuition():
            return
            
        activity_id = self._select_activity()
        if not activity_id:
            return
            
        metric_id = self._select_metric()
        if not metric_id:
            return
        
        # Get direction
        direction = Prompt.ask(
            self.DIRECTION_OF_INFLUENCE,
            choices=["positive", "negative"],
            default="positive"
        )
        
        data = {
            "account_id": self.account_id,
            "activity_id": activity_id,
            "metric_id": metric_id,
            "direction": direction
        }
        
        # Show preview
        self._show_data_preview("Intuition", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.create_intuition(data)
                console.print("[green]Intuition created successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to create intuition: {e}[/red]")
    
    def _check_required_entities_for_intuition(self):
        """Check if required entities exist for creating intuitions."""
        # Check for activities
        activities_response = self.client.get_activities(self.account_id)
        activities = activities_response.get("activities", [])
        
        if not activities:
            console.print(self.NO_ACTIVITIES_FOUND)
            return False
        
        # Check for metrics
        metrics_response = self.client.get_metrics(self.account_id)
        metrics = metrics_response.get("metrics", [])
        
        if not metrics:
            console.print("[yellow]No metrics found. Create metrics first.[/yellow]")
            return False
            
        return True
    
    def _select_activity(self):
        """Select an activity for intuition creation."""
        activities_response = self.client.get_activities(self.account_id)
        activities = activities_response.get("activities", [])
        
        if not activities:
            return None
        
        console.print("\n[bold]Select Activity:[/bold]")
        for i, activity in enumerate(activities, 1):
            activity_desc = activity.get("activity_description", "N/A")
            if len(activity_desc) > 50:
                activity_desc = activity_desc[:50] + "..."
            console.print(f"{i}. {activity_desc}")
        
        choice = Prompt.ask(
            self.ENTER_ACTIVITY_NUMBER,
            choices=[str(i) for i in range(1, len(activities) + 1)]
        )
        
        selected_activity = activities[int(choice) - 1]
        return selected_activity.get("id")
    
    def _edit_intuition(self):
        """Edit an existing intuition (Activity → Metric relationship)."""
        response = self.client.get_insights(self.account_id)
        intuitions = response.get("intuitions", [])
        
        if not intuitions:
            console.print("[yellow]No intuitions found to edit.[/yellow]")
            return
        
        # Select intuition to edit
        console.print("\n[bold]Select Intuition to Edit:[/bold]")
        for i, intuition in enumerate(intuitions, 1):
            activity_id = intuition.get("activity_id", "N/A")
            metric_id = intuition.get("metric_id", "N/A")
            direction = intuition.get("direction", "N/A")
            console.print(f"{i}. {activity_id} → {metric_id} ({direction})")
        
        choice = Prompt.ask(
            "Enter intuition number",
            choices=[str(i) for i in range(1, len(intuitions) + 1)]
        )
        
        intuition = intuitions[int(choice) - 1]
        activity_id = intuition.get("activity_id")
        metric_id = intuition.get("metric_id")
        
        # Edit direction
        current_direction = intuition.get("direction", "positive")
        direction = Prompt.ask(
            self.DIRECTION_OF_INFLUENCE,
            choices=["positive", "negative"],
            default=current_direction
        )
        
        data = {
            "account_id": self.account_id,
            "activity_id": activity_id,
            "metric_id": metric_id,
            "direction": direction
        }
        
        self._show_data_preview("Updated Intuition", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                self.client.update_intuition(data)
                console.print("[green]Intuition updated successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to update intuition: {e}[/red]")
    
    def _delete_intuition(self):
        """Delete an intuition (Activity → Metric relationship)."""
        response = self.client.get_insights(self.account_id)
        intuitions = response.get("intuitions", [])
        
        if not intuitions:
            console.print("[yellow]No intuitions found to delete.[/yellow]")
            return
        
        # Select intuition to delete
        console.print("\n[bold]Select Intuition to Delete:[/bold]")
        for i, intuition in enumerate(intuitions, 1):
            activity_id = intuition.get("activity_id", "N/A")
            metric_id = intuition.get("metric_id", "N/A")
            direction = intuition.get("direction", "N/A")
            console.print(f"{i}. {activity_id} → {metric_id} ({direction})")
        
        choice = Prompt.ask(
            "Enter intuition number",
            choices=[str(i) for i in range(1, len(intuitions) + 1)]
        )
        
        intuition = intuitions[int(choice) - 1]
        activity_id = intuition.get("activity_id")
        metric_id = intuition.get("metric_id")
        
        console.print(f"\n[bold red]DELETE Intuition: {activity_id} → {metric_id}[/bold red]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        if Confirm.ask("Are you sure you want to delete this intuition?"):
            data = {
                "account_id": self.account_id,
                "activity_id": activity_id,
                "metric_id": metric_id
            }
            
            try:
                self.client.delete_intuition(data)
                console.print("[green]Intuition deleted successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to delete intuition: {e}[/red]")
    
    # Firestore Management Methods
    
    def _manage_kpi_settings(self):
        """Manage KPI settings."""
        while True:
            console.print(f"\n[bold]KPI Settings Management:[/bold]")
            console.print("1. View All KPI Settings")
            console.print("2. Update KPI Setting")
            console.print("3. Back to Main Menu")
            
            choice = Prompt.ask(self.CHOOSE_OPTION_PROMPT, choices=["1", "2", "3"])
            
            if choice == "1":
                self._view_kpi_settings()
            elif choice == "2":
                self._update_kpi_setting()
            elif choice == "3":
                break
    
    def _view_kpi_settings(self):
        """View all KPI settings."""
        try:
            result = self.client.get_all_kpi_settings(self.account_id)
            if result.get("success"):
                kpi_settings = result.get("kpi_settings", {})
                if kpi_settings:
                    table = Table(title="KPI Settings")
                    table.add_column("KPI Name", style="cyan")
                    table.add_column("Metric ID", style="yellow")
                    
                    for kpi_name, metric_id in kpi_settings.items():
                        table.add_row(kpi_name, metric_id)
                    
                    console.print(table)
                else:
                    console.print("[yellow]No KPI settings found.[/yellow]")
            else:
                console.print(f"[red]Error: {result.get('detail', 'Unknown error')}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to retrieve KPI settings: {e}[/red]")
    
    def _update_kpi_setting(self):
        """Update a KPI setting."""
        console.print("\n[bold]Update KPI Setting[/bold]")
        
        kpi_name = Prompt.ask(
            "KPI Name",
            choices=["income_kpi", "marketing_cost_kpi", "net_income_kpi"]
        )
        
        metric_id = Prompt.ask("Metric ID")
        
        data = {
            "account_id": self.account_id,
            "kpi_name": kpi_name,
            "metric_id": metric_id
        }
        
        self._show_data_preview("KPI Setting", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.update_kpi_setting(data)
                if result.get("success"):
                    console.print("[green]KPI setting updated successfully![/green]")
                else:
                    console.print(f"[red]Failed to update KPI setting: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to update KPI setting: {e}[/red]")
    
    def _manage_funnel_steps(self):
        """Manage funnel steps."""
        while True:
            choice = self._show_crud_menu("Funnel Steps")
            if choice == "1":
                self._view_funnel_steps()
            elif choice == "2":
                self._add_funnel_step()
            elif choice == "3":
                self._edit_funnel_step()
            elif choice == "4":
                self._delete_funnel_step()
            elif choice == "5":
                break
    
    def _view_funnel_steps(self):
        """View all funnel steps."""
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        try:
            result = self.client.get_funnel_steps(self.account_id, funnel_type, big_bet_name)
            if result.get("success"):
                funnel_steps = result.get("funnel_steps", [])
                if funnel_steps:
                    table = Table(title=f"Funnel Steps ({funnel_type})")
                    table.add_column("Step #", style="cyan")
                    table.add_column("Step Name", style="yellow")
                    table.add_column("Objective", style="magenta", max_width=50)
                    table.add_column("Effectiveness KPI", style="green")
                    table.add_column("Efficiency KPI", style="blue")
                    
                    for step in funnel_steps:
                        table.add_row(
                            str(step.get("funnel_step_num", "")),
                            step.get("step_name", ""),
                            step.get("objective", ""),
                            step.get("effectiveness_kpi", ""),
                            step.get("efficiency_kpi", "")
                        )
                    
                    console.print(table)
                else:
                    console.print("[yellow]No funnel steps found.[/yellow]")
            else:
                console.print(f"[red]Error: {result.get('detail', 'Unknown error')}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to retrieve funnel steps: {e}[/red]")
    
    def _add_funnel_step(self):
        """Add a new funnel step."""
        console.print("\n[bold]Add New Funnel Step[/bold]")
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        funnel_step_name = Prompt.ask(
            "Funnel Step Name",
            choices=["awareness", "consideration", "conversion", "loyalty"]
        )
        effectiveness_kpi = Prompt.ask("Effectiveness KPI (Metric ID)")
        efficiency_kpi = Prompt.ask("Efficiency KPI (Metric ID)")
        objective = Prompt.ask("Objective")
        
        data = {
            "account_id": self.account_id,
            "funnel_type": funnel_type,
            "funnel_step_num": funnel_step_num,
            "funnel_step_name": funnel_step_name,
            "effectiveness_kpi": effectiveness_kpi,
            "efficiency_kpi": efficiency_kpi,
            "objective": objective
        }
        
        if big_bet_name:
            data["big_bet_name"] = big_bet_name
        
        self._show_data_preview("Funnel Step", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.create_funnel_step(data)
                if result.get("success"):
                    console.print("[green]Funnel step created successfully![/green]")
                else:
                    console.print(f"[red]Failed to create funnel step: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to create funnel step: {e}[/red]")
    
    def _edit_funnel_step(self):
        """Edit an existing funnel step."""
        console.print("\n[bold]Edit Funnel Step[/bold]")
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        
        # Get current data
        try:
            current_result = self.client.get_funnel_step(self.account_id, funnel_type, funnel_step_num, big_bet_name)
            if not current_result.get("success"):
                console.print("[red]Funnel step not found.[/red]")
                return
            
            current_data = current_result.get("funnel_step_data", {})
        except Exception as e:
            console.print(f"[red]Failed to get current funnel step: {e}[/red]")
            return
        
        # Prompt for new values
        funnel_step_name = Prompt.ask(
            "Funnel Step Name",
            choices=["awareness", "consideration", "conversion", "loyalty"],
            default=current_data.get("funnel_step_name", "")
        )
        effectiveness_kpi = Prompt.ask(
            "Effectiveness KPI (Metric ID)",
            default=current_data.get("effectiveness_kpi", "")
        )
        efficiency_kpi = Prompt.ask(
            "Efficiency KPI (Metric ID)",
            default=current_data.get("efficiency_kpi", "")
        )
        objective = Prompt.ask(
            "Objective",
            default=current_data.get("objective", "")
        )
        
        data = {
            "account_id": self.account_id,
            "funnel_type": funnel_type,
            "funnel_step_num": funnel_step_num,
            "funnel_step_name": funnel_step_name,
            "effectiveness_kpi": effectiveness_kpi,
            "efficiency_kpi": efficiency_kpi,
            "objective": objective
        }
        
        if big_bet_name:
            data["big_bet_name"] = big_bet_name
        
        self._show_data_preview("Updated Funnel Step", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.update_funnel_step(self.account_id, funnel_type, funnel_step_num, data, big_bet_name)
                if result.get("success"):
                    console.print("[green]Funnel step updated successfully![/green]")
                else:
                    console.print(f"[red]Failed to update funnel step: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to update funnel step: {e}[/red]")
    
    def _delete_funnel_step(self):
        """Delete a funnel step."""
        console.print("\n[bold]Delete Funnel Step[/bold]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        
        if Confirm.ask("Are you sure you want to delete this funnel step?"):
            try:
                result = self.client.delete_funnel_step(self.account_id, funnel_type, funnel_step_num, big_bet_name)
                if result.get("success"):
                    console.print("[green]Funnel step deleted successfully![/green]")
                else:
                    console.print(f"[red]Failed to delete funnel step: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to delete funnel step: {e}[/red]")
    
    def _manage_channels(self):
        """Manage channels."""
        while True:
            choice = self._show_crud_menu("Channels")
            if choice == "1":
                self._view_channels()
            elif choice == "2":
                self._add_channel()
            elif choice == "3":
                self._edit_channel()
            elif choice == "4":
                self._delete_channel()
            elif choice == "5":
                break
    
    def _view_channels(self):
        """View all channels in a funnel step."""
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        
        try:
            result = self.client.get_channels(self.account_id, funnel_type, funnel_step_num, big_bet_name)
            if result.get("channels"):
                channels = result.get("channels", [])
                if channels:
                    table = Table(title=f"Channels (Step {funnel_step_num})")
                    table.add_column("Channel Name", style="cyan")
                    table.add_column("Effectiveness KPI", style="yellow")
                    table.add_column("Efficiency KPI", style="green")
                    table.add_column("Supporting Metrics", style="blue")
                    
                    for channel in channels:
                        supporting_metrics = ", ".join(channel.get("supporting_metrics", []))
                        table.add_row(
                            channel.get("channel_name", ""),
                            channel.get("effectiveness_kpi", ""),
                            channel.get("efficiency_kpi", ""),
                            supporting_metrics
                        )
                    
                    console.print(table)
                else:
                    console.print("[yellow]No channels found.[/yellow]")
            else:
                console.print(f"[red]Error: {result.get('detail', 'Unknown error')}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to retrieve channels: {e}[/red]")
    
    def _add_channel(self):
        """Add a new channel."""
        console.print("\n[bold]Add New Channel[/bold]")
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        effectiveness_kpi = Prompt.ask("Effectiveness KPI (Metric ID)")
        efficiency_kpi = Prompt.ask("Efficiency KPI (Metric ID)")
        
        # Get supporting metrics
        supporting_metrics = self._prompt_for_list_input("Supporting Metrics (Metric IDs)")
        
        data = {
            "channel_name": channel_name,
            "effectiveness_kpi": effectiveness_kpi,
            "efficiency_kpi": efficiency_kpi,
            "supporting_metrics": supporting_metrics
        }
        
        self._show_data_preview("Channel", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.create_channel(data, self.account_id, funnel_type, funnel_step_num, big_bet_name)
                if result.get("success"):
                    console.print("[green]Channel created successfully![/green]")
                else:
                    console.print(f"[red]Failed to create channel: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to create channel: {e}[/red]")
    
    def _edit_channel(self):
        """Edit an existing channel."""
        console.print("\n[bold]Edit Channel[/bold]")
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        
        # Get current data
        try:
            current_result = self.client.get_channel(channel_name, self.account_id, funnel_type, funnel_step_num, big_bet_name)
            if not current_result.get("success"):
                console.print("[red]Channel not found.[/red]")
                return
            
            current_data = current_result.get("channel_data", {})
        except Exception as e:
            console.print(f"[red]Failed to get current channel: {e}[/red]")
            return
        
        # Prompt for new values
        effectiveness_kpi = Prompt.ask(
            "Effectiveness KPI (Metric ID)",
            default=current_data.get("effectiveness_kpi", "")
        )
        efficiency_kpi = Prompt.ask(
            "Efficiency KPI (Metric ID)",
            default=current_data.get("efficiency_kpi", "")
        )
        
        # Get supporting metrics
        supporting_metrics = self._prompt_for_list_input(
            "Supporting Metrics (Metric IDs)",
            default=current_data.get("supporting_metrics", [])
        )
        
        data = {
            "effectiveness_kpi": effectiveness_kpi,
            "efficiency_kpi": efficiency_kpi,
            "supporting_metrics": supporting_metrics
        }
        
        self._show_data_preview("Updated Channel", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.update_channel(channel_name, data, self.account_id, funnel_type, funnel_step_num, big_bet_name)
                if result.get("success"):
                    console.print("[green]Channel updated successfully![/green]")
                else:
                    console.print(f"[red]Failed to update channel: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to update channel: {e}[/red]")
    
    def _delete_channel(self):
        """Delete a channel."""
        console.print("\n[bold]Delete Channel[/bold]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        
        if Confirm.ask("Are you sure you want to delete this channel?"):
            try:
                result = self.client.delete_channel(channel_name, self.account_id, funnel_type, funnel_step_num, big_bet_name)
                if result.get("success"):
                    console.print("[green]Channel deleted successfully![/green]")
                else:
                    console.print(f"[red]Failed to delete channel: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to delete channel: {e}[/red]")
    
    def _manage_tactics(self):
        """Manage tactics."""
        while True:
            choice = self._show_crud_menu("Tactics")
            if choice == "1":
                self._view_tactics()
            elif choice == "2":
                self._add_tactic()
            elif choice == "3":
                self._edit_tactic()
            elif choice == "4":
                self._delete_tactic()
            elif choice == "5":
                break
    
    def _view_tactics(self):
        """View all tactics in a channel."""
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        
        try:
            result = self.client.get_tactics(self.account_id, funnel_type, funnel_step_num, channel_name, big_bet_name)
            if result.get("tactics"):
                tactics = result.get("tactics", [])
                if tactics:
                    table = Table(title=f"Tactics (Channel: {channel_name})")
                    table.add_column("Tactic Name", style="cyan")
                    table.add_column("Effectiveness KPI", style="yellow")
                    table.add_column("Efficiency KPI", style="green")
                    table.add_column("Supporting Metrics", style="blue")
                    
                    for tactic in tactics:
                        supporting_metrics = ", ".join(tactic.get("supporting_metrics", []))
                        table.add_row(
                            tactic.get("tactic_name", ""),
                            tactic.get("effectiveness_kpi", ""),
                            tactic.get("efficiency_kpi", ""),
                            supporting_metrics
                        )
                    
                    console.print(table)
                else:
                    console.print("[yellow]No tactics found.[/yellow]")
            else:
                console.print(f"[red]Error: {result.get('detail', 'Unknown error')}[/red]")
        except Exception as e:
            console.print(f"[red]Failed to retrieve tactics: {e}[/red]")
    
    def _add_tactic(self):
        """Add a new tactic."""
        console.print("\n[bold]Add New Tactic[/bold]")
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        tactic_name = Prompt.ask("Tactic Name")
        effectiveness_kpi = Prompt.ask("Effectiveness KPI (Metric ID)")
        efficiency_kpi = Prompt.ask("Efficiency KPI (Metric ID)")
        
        # Get supporting metrics
        supporting_metrics = self._prompt_for_list_input("Supporting Metrics (Metric IDs)")
        
        data = {
            "tactic_name": tactic_name,
            "effectiveness_kpi": effectiveness_kpi,
            "efficiency_kpi": efficiency_kpi,
            "supporting_metrics": supporting_metrics
        }
        
        self._show_data_preview("Tactic", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.create_tactic(data, self.account_id, funnel_type, funnel_step_num, channel_name, big_bet_name)
                if result.get("success"):
                    console.print("[green]Tactic created successfully![/green]")
                else:
                    console.print(f"[red]Failed to create tactic: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to create tactic: {e}[/red]")
    
    def _edit_tactic(self):
        """Edit an existing tactic."""
        console.print("\n[bold]Edit Tactic[/bold]")
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        tactic_name = Prompt.ask("Tactic Name")
        
        # Get current data
        try:
            current_result = self.client.get_tactic(tactic_name, self.account_id, funnel_type, funnel_step_num, channel_name, big_bet_name)
            if not current_result.get("success"):
                console.print("[red]Tactic not found.[/red]")
                return
            
            current_data = current_result.get("tactic_data", {})
        except Exception as e:
            console.print(f"[red]Failed to get current tactic: {e}[/red]")
            return
        
        # Prompt for new values
        effectiveness_kpi = Prompt.ask(
            "Effectiveness KPI (Metric ID)",
            default=current_data.get("effectiveness_kpi", "")
        )
        efficiency_kpi = Prompt.ask(
            "Efficiency KPI (Metric ID)",
            default=current_data.get("efficiency_kpi", "")
        )
        
        # Get supporting metrics
        supporting_metrics = self._prompt_for_list_input(
            "Supporting Metrics (Metric IDs)",
            default=current_data.get("supporting_metrics", [])
        )
        
        data = {
            "effectiveness_kpi": effectiveness_kpi,
            "efficiency_kpi": efficiency_kpi,
            "supporting_metrics": supporting_metrics
        }
        
        self._show_data_preview("Updated Tactic", data)
        
        if Confirm.ask(self.SAVE_CHANGES_PROMPT):
            try:
                result = self.client.update_tactic(tactic_name, data, self.account_id, funnel_type, funnel_step_num, channel_name, big_bet_name)
                if result.get("success"):
                    console.print("[green]Tactic updated successfully![/green]")
                else:
                    console.print(f"[red]Failed to update tactic: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to update tactic: {e}[/red]")
    
    def _delete_tactic(self):
        """Delete a tactic."""
        console.print("\n[bold]Delete Tactic[/bold]")
        console.print(self.CANNOT_UNDONE_WARNING)
        
        funnel_type = Prompt.ask("Funnel Type", choices=["organization", "big_bet"])
        big_bet_name = None
        if funnel_type == "big_bet":
            big_bet_name = Prompt.ask("Big Bet Name")
        
        funnel_step_num = int(Prompt.ask("Funnel Step Number"))
        channel_name = Prompt.ask("Channel Name")
        tactic_name = Prompt.ask("Tactic Name")
        
        if Confirm.ask("Are you sure you want to delete this tactic?"):
            try:
                result = self.client.delete_tactic(tactic_name, self.account_id, funnel_type, funnel_step_num, channel_name, big_bet_name)
                if result.get("success"):
                    console.print("[green]Tactic deleted successfully![/green]")
                else:
                    console.print(f"[red]Failed to delete tactic: {result.get('detail', 'Unknown error')}[/red]")
            except Exception as e:
                console.print(f"[red]Failed to delete tactic: {e}[/red]")
    
    def _prompt_for_list_input(self, prompt: str, default: Optional[List[str]] = None) -> List[str]:
        """Prompt for list input with comma separation."""
        if default is None:
            default = []
        
        default_str = ", ".join(default)
        input_str = Prompt.ask(f"{prompt} (comma-separated)", default=default_str)
        
        if not input_str.strip():
            return []
        
        return [item.strip() for item in input_str.split(",") if item.strip()]
    
    # Utility methods
    def _show_data_preview(self, title: str, data: Dict[str, Any]):
        """Show a preview of data before confirmation."""
        console.print(f"\n[bold]{title} Preview:[/bold]")
        
        table = Table(show_header=False)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="yellow")
        
        for key, value in data.items():
            if key == "account_id":  # Skip account_id in preview
                continue
            table.add_row(key.replace("_", " ").title(), str(value))
        
        console.print(table)
    
    def _get_list_input(self, prompt: str, default: Optional[List[str]] = None) -> List[str]:
        """Get a list input from user."""
        if default is None:
            default = []
        
        default_str = ", ".join(default)
        input_str = Prompt.ask(f"{prompt} (comma-separated)", default=default_str)
        
        if not input_str.strip():
            return []
        
        return [item.strip() for item in input_str.split(",") if item.strip()]


def main():
    """Main entry point."""
    try:
        cli = KeneCLI()
        cli.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
