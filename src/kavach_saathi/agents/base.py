from __future__ import annotations

from dataclasses import dataclass

from kavach_saathi.config import Settings
from kavach_saathi.providers.external import ExternalProvider
from kavach_saathi.providers.media import MediaProvider
from kavach_saathi.providers.reasoning import ReasoningProvider
from kavach_saathi.repository import CommerceRepository


@dataclass(slots=True)
class AgentContext:
    settings: Settings
    repository: CommerceRepository
    reasoner: ReasoningProvider
    media: MediaProvider
    external: ExternalProvider


class Agent:
    def __init__(self, context: AgentContext):
        self.context = context
