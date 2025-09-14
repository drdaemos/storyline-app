import tempfile
import uuid
from pathlib import Path

import pytest

from src.summary_memory import SummaryMemory


class TestSummaryMemory:

    def setup_method(self):
        """Set up a temporary memory directory with test database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        # Create custom memory instance that uses summaries_test.db
        self.memory = SummaryMemory(memory_dir=Path(self.temp_dir))
        # Override the db_path to use test database
        self.memory.db_path = self.memory.memory_dir / "summaries_test.db"
        # Initialize the test database
        self.memory._init_database()
        self.character_id = "test_character"
        self.session_id = str(uuid.uuid4())

    def teardown_method(self):
        """Clean up test database file."""
        # Close any open connections first
        self.memory.close()
        # Remove the entire test database file
        if self.memory.db_path.exists():
            try:
                self.memory.db_path.unlink()
            except PermissionError:
                # File might still be locked, ignore for now
                pass

    def test_init_default_directory(self):
        """Test initialization with default directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            memory = None
            try:
                # Change to temp directory
                import os
                os.chdir(temp_dir)

                memory = SummaryMemory()
                expected_path = Path(temp_dir) / "memory" / "summaries.db"
                # Resolve both paths to handle symlinks (like /var -> /private/var on macOS)
                assert memory.db_path.resolve() == expected_path.resolve()
                # Close the database connection to prevent permission errors on Windows
                memory.close()
                memory = None
                # Force garbage collection to help with Windows file locking issues
                import gc
                gc.collect()
            finally:
                if memory:
                    memory.close()
                os.chdir(original_cwd)

    def test_init_custom_directory(self):
        """Test initialization with custom directory."""
        custom_dir = Path(self.temp_dir) / "custom_summary_memory"
        memory = SummaryMemory(memory_dir=custom_dir)

        assert memory.memory_dir == custom_dir
        assert memory.db_path == custom_dir / "summaries.db"
        assert custom_dir.exists()

    def test_add_summary_valid(self):
        """Test adding a valid summary."""
        summary_id = self.memory.add_summary(
            self.character_id,
            self.session_id,
            "User introduced themselves and asked about the case.",
            0,
            2
        )

        assert isinstance(summary_id, int)
        assert summary_id > 0

    def test_add_summary_invalid_offsets(self):
        """Test adding summary with invalid offset values."""
        # Test negative offsets
        with pytest.raises(ValueError, match="Offsets must be non-negative"):
            self.memory.add_summary(
                self.character_id,
                self.session_id,
                "Invalid summary",
                -1,
                2
            )

        with pytest.raises(ValueError, match="Offsets must be non-negative"):
            self.memory.add_summary(
                self.character_id,
                self.session_id,
                "Invalid summary",
                0,
                -1
            )

        # Test start_offset > end_offset
        with pytest.raises(ValueError, match="start_offset must be <= end_offset"):
            self.memory.add_summary(
                self.character_id,
                self.session_id,
                "Invalid summary",
                5,
                2
            )

    def test_get_session_summaries(self):
        """Test retrieving summaries for a session."""
        # Add multiple summaries
        self.memory.add_summary(self.character_id, self.session_id, "First summary", 0, 3)
        self.memory.add_summary(self.character_id, self.session_id, "Second summary", 4, 7)
        self.memory.add_summary(self.character_id, self.session_id, "Third summary", 8, 10)

        summaries = self.memory.get_session_summaries(self.session_id)

        assert len(summaries) == 3
        # Should be ordered by start_offset
        assert summaries[0]["summary"] == "First summary"
        assert summaries[0]["start_offset"] == 0
        assert summaries[0]["end_offset"] == 3
        assert summaries[1]["summary"] == "Second summary"
        assert summaries[1]["start_offset"] == 4
        assert summaries[2]["summary"] == "Third summary"
        assert summaries[2]["start_offset"] == 8

        # Check all required fields are present
        for summary in summaries:
            assert "id" in summary
            assert "character_id" in summary
            assert "session_id" in summary
            assert "summary" in summary
            assert "start_offset" in summary
            assert "end_offset" in summary
            assert "created_at" in summary

    def test_get_session_summaries_empty(self):
        """Test retrieving summaries for session with no summaries."""
        summaries = self.memory.get_session_summaries(self.session_id)
        assert summaries == []

    def test_get_character_summaries(self):
        """Test retrieving summaries for a character."""
        session1 = str(uuid.uuid4())
        session2 = str(uuid.uuid4())

        # Add summaries to different sessions
        self.memory.add_summary(self.character_id, session1, "Session 1 summary", 0, 2)
        self.memory.add_summary(self.character_id, session2, "Session 2 summary", 0, 4)
        self.memory.add_summary(self.character_id, session1, "Session 1 summary 2", 3, 5)

        summaries = self.memory.get_character_summaries(self.character_id)

        assert len(summaries) == 3
        # Should be ordered by created_at DESC (most recent first)
        # Since they're created quickly, we'll just check all are present
        summary_texts = [s["summary"] for s in summaries]
        assert "Session 1 summary" in summary_texts
        assert "Session 2 summary" in summary_texts
        assert "Session 1 summary 2" in summary_texts

    def test_get_character_summaries_with_limit(self):
        """Test retrieving character summaries with limit."""
        # Add multiple summaries
        for i in range(5):
            self.memory.add_summary(self.character_id, self.session_id, f"Summary {i}", i*2, i*2+1)

        summaries = self.memory.get_character_summaries(self.character_id, limit=3)
        assert len(summaries) == 3

    def test_get_character_summaries_no_summaries(self):
        """Test retrieving summaries for character with no summaries."""
        summaries = self.memory.get_character_summaries("nonexistent_character")
        assert summaries == []

    def test_get_summaries_covering_offset(self):
        """Test getting summaries that cover a specific offset."""
        # Add summaries with different ranges
        self.memory.add_summary(self.character_id, self.session_id, "Summary 1", 0, 5)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 2", 3, 8)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 3", 10, 15)

        # Test offset that's covered by multiple summaries
        covering_summaries = self.memory.get_summaries_covering_offset(self.session_id, 4)
        assert len(covering_summaries) == 2
        summary_texts = [s["summary"] for s in covering_summaries]
        assert "Summary 1" in summary_texts
        assert "Summary 2" in summary_texts

        # Test offset covered by one summary
        covering_summaries = self.memory.get_summaries_covering_offset(self.session_id, 12)
        assert len(covering_summaries) == 1
        assert covering_summaries[0]["summary"] == "Summary 3"

        # Test offset not covered by any summary
        covering_summaries = self.memory.get_summaries_covering_offset(self.session_id, 9)
        assert len(covering_summaries) == 0

    def test_get_summaries_in_range(self):
        """Test getting summaries that overlap with a range."""
        # Add summaries with different ranges
        self.memory.add_summary(self.character_id, self.session_id, "Summary 1", 0, 3)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 2", 5, 8)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 3", 10, 15)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 4", 2, 6)

        # Test range that overlaps with multiple summaries
        overlapping_summaries = self.memory.get_summaries_in_range(self.session_id, 2, 6)
        assert len(overlapping_summaries) == 3  # Summary 1, 2, and 4
        summary_texts = [s["summary"] for s in overlapping_summaries]
        assert "Summary 1" in summary_texts
        assert "Summary 2" in summary_texts
        assert "Summary 4" in summary_texts

        # Test range that doesn't overlap with any summary
        overlapping_summaries = self.memory.get_summaries_in_range(self.session_id, 16, 20)
        assert len(overlapping_summaries) == 0

        # Test range that partially overlaps
        overlapping_summaries = self.memory.get_summaries_in_range(self.session_id, 12, 20)
        assert len(overlapping_summaries) == 1
        assert overlapping_summaries[0]["summary"] == "Summary 3"

    def test_update_summary(self):
        """Test updating summary text."""
        # Add a summary
        summary_id = self.memory.add_summary(
            self.character_id,
            self.session_id,
            "Original summary",
            0,
            2
        )

        # Update the summary
        success = self.memory.update_summary(summary_id, "Updated summary text")
        assert success is True

        # Verify the update
        summaries = self.memory.get_session_summaries(self.session_id)
        assert len(summaries) == 1
        assert summaries[0]["summary"] == "Updated summary text"
        assert summaries[0]["id"] == summary_id

    def test_update_nonexistent_summary(self):
        """Test updating a nonexistent summary."""
        success = self.memory.update_summary(999, "New text")
        assert success is False

    def test_delete_summary(self):
        """Test deleting a summary."""
        # Add summaries
        summary_id1 = self.memory.add_summary(self.character_id, self.session_id, "Summary 1", 0, 2)
        summary_id2 = self.memory.add_summary(self.character_id, self.session_id, "Summary 2", 3, 5)

        # Delete one summary
        success = self.memory.delete_summary(summary_id1)
        assert success is True

        # Verify only one summary remains
        summaries = self.memory.get_session_summaries(self.session_id)
        assert len(summaries) == 1
        assert summaries[0]["id"] == summary_id2

    def test_delete_nonexistent_summary(self):
        """Test deleting a nonexistent summary."""
        success = self.memory.delete_summary(999)
        assert success is False

    def test_delete_session_summaries(self):
        """Test deleting all summaries for a session."""
        session2 = str(uuid.uuid4())

        # Add summaries to multiple sessions
        self.memory.add_summary(self.character_id, self.session_id, "Session 1 Summary 1", 0, 2)
        self.memory.add_summary(self.character_id, self.session_id, "Session 1 Summary 2", 3, 5)
        self.memory.add_summary(self.character_id, session2, "Session 2 Summary", 0, 2)

        # Delete summaries for one session
        deleted_count = self.memory.delete_session_summaries(self.session_id)
        assert deleted_count == 2

        # Verify session1 summaries are gone
        session1_summaries = self.memory.get_session_summaries(self.session_id)
        assert len(session1_summaries) == 0

        # Verify session2 summaries remain
        session2_summaries = self.memory.get_session_summaries(session2)
        assert len(session2_summaries) == 1

    def test_clear_character_summaries(self):
        """Test deleting all summaries for a character."""
        character2 = "character2"

        # Add summaries for multiple characters
        self.memory.add_summary(self.character_id, self.session_id, "Character 1 Summary", 0, 2)
        self.memory.add_summary(character2, self.session_id, "Character 2 Summary", 0, 2)

        # Clear summaries for one character
        deleted_count = self.memory.clear_character_summaries(self.character_id)
        assert deleted_count == 1

        # Verify character1 summaries are gone
        char1_summaries = self.memory.get_character_summaries(self.character_id)
        assert len(char1_summaries) == 0

        # Verify character2 summaries remain
        char2_summaries = self.memory.get_character_summaries(character2)
        assert len(char2_summaries) == 1

    def test_get_max_processed_offset(self):
        """Test getting the maximum processed offset for a session."""
        # Test session with no summaries
        max_offset = self.memory.get_max_processed_offset(self.session_id)
        assert max_offset is None

        # Add summaries with different end offsets
        self.memory.add_summary(self.character_id, self.session_id, "Summary 1", 0, 5)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 2", 6, 10)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 3", 11, 15)

        max_offset = self.memory.get_max_processed_offset(self.session_id)
        assert max_offset == 15

        # Add a summary with a lower end offset (shouldn't change max)
        self.memory.add_summary(self.character_id, self.session_id, "Summary 4", 2, 8)
        max_offset = self.memory.get_max_processed_offset(self.session_id)
        assert max_offset == 15

    def test_database_persistence(self):
        """Test that data persists across memory instance recreation."""
        # Add a summary
        original_summary_id = self.memory.add_summary(
            self.character_id,
            self.session_id,
            "Persistent summary",
            0,
            3
        )

        # Create new memory instance with same directory and test database
        new_memory = SummaryMemory(memory_dir=Path(self.temp_dir))
        new_memory.db_path = new_memory.memory_dir / "summaries_test.db"

        # Verify data persists
        summaries = new_memory.get_session_summaries(self.session_id)
        assert len(summaries) == 1
        assert summaries[0]["summary"] == "Persistent summary"
        assert summaries[0]["id"] == original_summary_id

    def test_close_method(self):
        """Test the close method (currently no-op)."""
        # Should not raise an exception
        self.memory.close()

    def test_summary_ordering_consistency(self):
        """Test that summaries are consistently ordered."""
        # Add summaries out of offset order
        self.memory.add_summary(self.character_id, self.session_id, "Summary C", 20, 25)
        self.memory.add_summary(self.character_id, self.session_id, "Summary A", 0, 5)
        self.memory.add_summary(self.character_id, self.session_id, "Summary B", 10, 15)

        summaries = self.memory.get_session_summaries(self.session_id)

        # Should be ordered by start_offset regardless of insertion order
        assert len(summaries) == 3
        assert summaries[0]["summary"] == "Summary A"
        assert summaries[0]["start_offset"] == 0
        assert summaries[1]["summary"] == "Summary B"
        assert summaries[1]["start_offset"] == 10
        assert summaries[2]["summary"] == "Summary C"
        assert summaries[2]["start_offset"] == 20

    def test_edge_case_single_message_summary(self):
        """Test creating a summary for a single message."""
        summary_id = self.memory.add_summary(
            self.character_id,
            self.session_id,
            "Single message summary",
            5,
            5  # start_offset == end_offset
        )

        summaries = self.memory.get_session_summaries(self.session_id)
        assert len(summaries) == 1
        assert summaries[0]["start_offset"] == 5
        assert summaries[0]["end_offset"] == 5

        # Test that it's found when querying for that offset
        covering = self.memory.get_summaries_covering_offset(self.session_id, 5)
        assert len(covering) == 1
        assert covering[0]["id"] == summary_id
