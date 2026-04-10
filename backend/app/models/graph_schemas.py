"""图谱导入与知识入图相关 Schema。"""

from pydantic import BaseModel, Field


class GraphNodeDraft(BaseModel):
    id: str = Field(default="", max_length=120)
    label: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=120)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)
    paper_title: str = Field(default="", max_length=300)


class GraphRelationDraft(BaseModel):
    from_id: str = Field(min_length=1, max_length=120)
    to_id: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=1000)
    source: str = Field(default="", max_length=120)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)
    paper_title: str = Field(default="", max_length=300)


class GraphDraftPayload(BaseModel):
    title: str = Field(default="", max_length=300)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source: str = Field(default="paper", max_length=120)
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)
    nodes: list[GraphNodeDraft] = Field(default_factory=list)
    relations: list[GraphRelationDraft] = Field(default_factory=list)


class GraphDraftRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    abstract: str = Field(default="", max_length=8000)
    content: str = Field(default="", max_length=30000)
    mode: str = Field(default="paper", pattern=r"^(paper|optimization)$")
    source: str = Field(default="paper", max_length=120)
    source_type: str = Field(default="", max_length=120)
    domain_tag: str = Field(default="", max_length=120)
    scenario: str = Field(default="", max_length=200)


class GraphExecuteRequest(BaseModel):
    graph: GraphDraftPayload
    cypher: str = Field(default="", max_length=50000)
    source: str = Field(default="", max_length=120)


class GraphQaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    max_nodes: int = Field(default=8, ge=3, le=16)
    max_relationships: int = Field(default=10, ge=2, le=20)


class GraphStrategyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    max_nodes: int = Field(default=10, ge=4, le=20)
    max_relationships: int = Field(default=12, ge=4, le=24)


class GraphSummaryResponse(BaseModel):
    ready: bool = False
    configured: bool = False
    dependency_installed: bool = False
    neo4j_connected: bool = False
    local_start_available: bool = False
    database: str = Field(default="", max_length=120)
    paper_count: int = 0
    node_count: int = 0
    relation_count: int = 0
    local_start_message: str = Field(default="", max_length=500)
    message: str = Field(default="", max_length=500)
