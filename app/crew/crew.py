# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# mypy: disable-error-code="attr-defined"
from typing import Any
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
#from crewai_tools import SerperDevTool, ScrapeWebsiteTool, FileWriterTool


@CrewBase
class AnalystCrew:
    """Analyst crew"""

    agents_config: dict[str, Any]
    tasks_config: dict[str, Any]

    llm = "vertex_ai/gemini-2.0-flash-001"

    # KEN-E -- Execution agent
    @agent
    def ken_e(self) -> Agent:
        return Agent(
            config=self.agents_config.get("ken_e"),
            allow_delegation=True,
            verbose=True,
            tools=[], # FileWriterTool()]
            llm=self.llm,
        )

    # BET-E -- Web Scraping Agent
    @agent
    def bet_e(self) -> Agent:
        return Agent(
            config=self.agents_config.get("bet_e"),
            allow_delegation=False,
            verbose=True,
            tools=[], # SerperDevTool(),ScrapeWebsiteTool()
            llm=self.llm,
        )

    # VIK-E -- Report writer
    @agent
    def vik_e(self) -> Agent:
        return Agent(
            config=self.agents_config.get("vik_e"),
            allow_delegation=False,
            verbose=True,
            tools=[],
            llm=self.llm,
        )

    @task
    def retrieve_news_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("retrieve_news_task"),
            agent=self.bet_e(),
        )

    @task
    def website_scrape_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("website_scrape_task"),
            agent=self.bet_e(),
        )

    @task
    def ai_news_write_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("ai_news_write_task"),
            agent=self.vik_e(),
        )

    @task
    def file_write_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("file_write_task"),
            agent=self.vik_e(),
            # output_file="report.md"
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Analyst Crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
