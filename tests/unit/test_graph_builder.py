"""
Tests for claude_graph_builder.py core functions
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import networkx as nx
import tempfile
import pickle

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier


class TestClaudeGraphBuilder:
    """Test ClaudeGraphBuilder class"""

    @pytest.mark.unit
    def test_initialization(self, mock_api_key):
        """Test graph builder initialization"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        assert builder.api_key == mock_api_key
        assert isinstance(builder.graph, nx.MultiDiGraph)
        assert builder.graph.number_of_nodes() == 0
        assert builder.graph.number_of_edges() == 0

    @pytest.mark.unit
    def test_add_entity(self, mock_api_key):
        """Test adding entity to graph"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        builder.add_entity("CAR-T Therapy", entity_type="treatment")

        assert builder.graph.has_node("CAR-T Therapy")
        node_data = builder.graph.nodes["CAR-T Therapy"]
        assert node_data['entity_type'] == "treatment"

    @pytest.mark.unit
    def test_add_duplicate_entity(self, mock_api_key):
        """Test adding duplicate entity updates existing"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        builder.add_entity("CAR-T Therapy", entity_type="treatment")
        builder.add_entity("CAR-T Therapy", entity_type="treatment", properties={'new_prop': 'value'})

        # Should still have only one node
        assert builder.graph.number_of_nodes() == 1
        # Should have updated properties
        node_data = builder.graph.nodes["CAR-T Therapy"]
        assert 'new_prop' in node_data

    @pytest.mark.unit
    def test_add_relationship(self, mock_api_key):
        """Test adding relationship between entities"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        builder.add_entity("CAR-T Therapy", entity_type="treatment")
        builder.add_entity("Lymphoma", entity_type="condition")
        builder.add_relationship("CAR-T Therapy", "Lymphoma", "treats")

        assert builder.graph.has_edge("CAR-T Therapy", "Lymphoma")
        edges = list(builder.graph.edges(data=True))
        assert len(edges) == 1
        assert edges[0][2]['relationship'] == 'treats'

    @pytest.mark.unit
    def test_get_entity_neighborhood(self, mock_api_key):
        """Test getting entity neighborhood"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        # Build small graph
        builder.add_entity("CAR-T Therapy", entity_type="treatment")
        builder.add_entity("Lymphoma", entity_type="condition")
        builder.add_entity("Immunotherapy", entity_type="treatment")
        builder.add_relationship("CAR-T Therapy", "Lymphoma", "treats")
        builder.add_relationship("CAR-T Therapy", "Immunotherapy", "part_of")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)
        neighborhood = querier.get_entity_neighborhood("CAR-T Therapy")

        assert neighborhood['entity'] == "CAR-T Therapy"
        assert len(neighborhood['outgoing']) == 2
        assert neighborhood['properties']['entity_type'] == "treatment"

    @pytest.mark.unit
    def test_find_paths(self, mock_api_key):
        """Test finding paths between entities"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        # Create a path: A -> B -> C
        builder.add_entity("A", entity_type="test")
        builder.add_entity("B", entity_type="test")
        builder.add_entity("C", entity_type="test")
        builder.add_relationship("A", "B", "relates_to")
        builder.add_relationship("B", "C", "relates_to")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)
        paths = querier.find_paths("A", "C", max_depth=3)

        assert len(paths) > 0
        # Should find path A -> B -> C
        assert ['A', 'B', 'C'] in paths

    @pytest.mark.unit
    def test_find_paths_no_path(self, mock_api_key):
        """Test finding paths when no path exists"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        # Create disconnected entities
        builder.add_entity("A", entity_type="test")
        builder.add_entity("Z", entity_type="test")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)
        paths = querier.find_paths("A", "Z", max_depth=3)

        assert len(paths) == 0

    @pytest.mark.unit
    def test_get_graph_stats(self, mock_api_key):
        """Test getting graph statistics"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        # Build small graph
        builder.add_entity("A", entity_type="test")
        builder.add_entity("B", entity_type="test")
        builder.add_entity("C", entity_type="test")
        builder.add_relationship("A", "B", "relates_to")
        builder.add_relationship("B", "C", "relates_to")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)
        stats = querier.get_graph_stats()

        assert stats['total_nodes'] == 3
        assert stats['total_edges'] == 2
        assert 'density' in stats
        assert 'top_entities' in stats

    @pytest.mark.unit
    def test_save_and_load_graph(self, mock_api_key):
        """Test saving and loading graph"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        # Build graph
        builder.add_entity("Test Entity", entity_type="test")
        builder.add_entity("Another Entity", entity_type="test")
        builder.add_relationship("Test Entity", "Another Entity", "relates_to")

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp:
            tmp_path = tmp.name

        try:
            builder.save_graph(tmp_path)

            # Load in new builder
            new_builder = ClaudeGraphBuilder(api_key=mock_api_key)
            new_builder.load_graph(tmp_path)

            # Verify
            assert new_builder.graph.number_of_nodes() == 2
            assert new_builder.graph.number_of_edges() == 1
            assert new_builder.graph.has_node("Test Entity")

        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestGraphProcessing:
    """Test graph processing and extraction"""

    @pytest.mark.unit
    @pytest.mark.requires_api
    @patch('claude_graph_builder.anthropic.Anthropic')
    def test_process_chunk_mocked(self, mock_anthropic_class, mock_api_key):
        """Test processing a chunk with mocked API"""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='{"entities": [{"name": "CAR-T", "type": "treatment"}], "relationships": [{"source": "CAR-T", "target": "Lymphoma", "type": "treats"}]}'
        )]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        chunk = "CAR-T therapy is used to treat lymphoma."

        result = builder.process_chunk(chunk)

        # Should have extracted entities and relationships
        assert result is not None
        assert builder.graph.number_of_nodes() > 0

    @pytest.mark.unit
    def test_clean_entity_name(self, mock_api_key):
        """Test entity name cleaning"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)

        # Test various cleaning scenarios
        cleaned = builder.clean_entity_name("  CAR-T Therapy  ")
        assert cleaned == "CAR-T Therapy"

        cleaned = builder.clean_entity_name("CAR-T\nTherapy")
        assert "\n" not in cleaned

    @pytest.mark.unit
    def test_merge_graphs(self, mock_api_key):
        """Test merging two graphs"""
        builder1 = ClaudeGraphBuilder(api_key=mock_api_key)
        builder1.add_entity("A", entity_type="test")
        builder1.add_entity("B", entity_type="test")
        builder1.add_relationship("A", "B", "relates_to")

        builder2 = ClaudeGraphBuilder(api_key=mock_api_key)
        builder2.add_entity("B", entity_type="test")
        builder2.add_entity("C", entity_type="test")
        builder2.add_relationship("B", "C", "relates_to")

        # Merge builder2 into builder1
        builder1.merge_graph(builder2.graph)

        # Should have all entities
        assert builder1.graph.number_of_nodes() == 3
        # Should have all relationships
        assert builder1.graph.number_of_edges() == 2
        assert builder1.graph.has_node("A")
        assert builder1.graph.has_node("B")
        assert builder1.graph.has_node("C")


class TestGraphQuerier:
    """Test ClaudeGraphQuerier functionality"""

    @pytest.mark.unit
    def test_search_entities(self, mock_api_key):
        """Test searching for entities"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        builder.add_entity("CAR-T Therapy", entity_type="treatment")
        builder.add_entity("Lymphoma Treatment", entity_type="treatment")
        builder.add_entity("Other Entity", entity_type="test")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)

        # Search for "therapy"
        results = []
        for node in querier.graph.nodes():
            if "therapy" in node.lower():
                results.append(node)

        assert "CAR-T Therapy" in results

    @pytest.mark.unit
    def test_get_entities_by_type(self, mock_api_key):
        """Test getting entities by type"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        builder.add_entity("CAR-T Therapy", entity_type="treatment")
        builder.add_entity("Lymphoma", entity_type="condition")
        builder.add_entity("Immunotherapy", entity_type="treatment")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)

        # Get all treatments
        treatments = [
            node for node, data in querier.graph.nodes(data=True)
            if data.get('entity_type') == 'treatment'
        ]

        assert len(treatments) == 2
        assert "CAR-T Therapy" in treatments
        assert "Immunotherapy" in treatments

    @pytest.mark.unit
    @patch('claude_graph_builder.anthropic.Anthropic')
    def test_query_with_claude_mocked(self, mock_anthropic_class, mock_api_key):
        """Test querying graph with Claude (mocked)"""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            text='CAR-T therapy is a treatment for lymphoma.'
        )]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        builder.add_entity("CAR-T Therapy", entity_type="treatment")
        builder.add_entity("Lymphoma", entity_type="condition")
        builder.add_relationship("CAR-T Therapy", "Lymphoma", "treats")

        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)
        result = querier.query_with_claude("What treats lymphoma?", max_entities=10)

        assert result is not None
        assert len(result) > 0


class TestGraphEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.unit
    def test_empty_graph_stats(self, mock_api_key):
        """Test stats on empty graph"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)

        stats = querier.get_graph_stats()

        assert stats['total_nodes'] == 0
        assert stats['total_edges'] == 0
        assert len(stats['top_entities']) == 0

    @pytest.mark.unit
    def test_self_loop(self, mock_api_key):
        """Test adding self-referential relationship"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        builder.add_entity("A", entity_type="test")
        builder.add_relationship("A", "A", "self_reference")

        assert builder.graph.has_edge("A", "A")

    @pytest.mark.unit
    def test_multiple_relationships_same_entities(self, mock_api_key):
        """Test multiple relationships between same entities"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        builder.add_entity("A", entity_type="test")
        builder.add_entity("B", entity_type="test")

        builder.add_relationship("A", "B", "relates_to")
        builder.add_relationship("A", "B", "part_of")

        # MultiDiGraph allows multiple edges
        edges = list(builder.graph.edges(data=True))
        assert len(edges) == 2

    @pytest.mark.unit
    def test_nonexistent_entity_neighborhood(self, mock_api_key):
        """Test getting neighborhood of non-existent entity"""
        builder = ClaudeGraphBuilder(api_key=mock_api_key)
        querier = ClaudeGraphQuerier(builder, api_key=mock_api_key)

        neighborhood = querier.get_entity_neighborhood("NonExistent")

        assert neighborhood['found'] is False
