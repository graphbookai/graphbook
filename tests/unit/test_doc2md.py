from graphbook.core.doc2md import convert_to_md


def test_convert_to_md_basic():
    """Test basic docstring conversion to markdown."""

    docstring = """
This is a simple docstring.
It has multiple lines.
"""

    expected = "This is a simple docstring.\nIt has multiple lines."
    assert convert_to_md(docstring) == expected


def test_convert_to_md_with_args():
    """Test conversion with Args section to check parameter formatting."""

    docstring = """
This is a docstring with args.

Args:
    param1: Description of param1
    param2: Description of param2
"""

    expected = """
This is a docstring with args.

**Parameters**
- **param1**: Description of param1
- **param2**: Description of param2
"""

    assert convert_to_md(docstring) == expected.strip()


def test_convert_to_md_with_returns():
    """Test conversion with Returns section."""

    docstring = """
This is a docstring with returns.

Returns:
    Description of return value
"""

    expected = """
This is a docstring with returns.

**Returns**
    Description of return value
"""
    assert convert_to_md(docstring) == expected.strip()


def test_convert_to_md_with_raises():
    """Test conversion with Raises section."""

    docstring = """
This is a docstring with raises.

Raises:
    ValueError: When something is wrong
"""

    expected = """
This is a docstring with raises.

**Raises**
    ValueError: When something is wrong
"""

    assert convert_to_md(docstring) == expected.strip()


def test_convert_to_md_complex():
    """Test conversion with multiple sections."""

    docstring = """
This is a complex docstring.

Args:
    param1: Description of param1
    param2: Description of param2

Returns:
    The processed result

Raises:
    ValueError: When something is wrong
"""

    expected = """
This is a complex docstring.

**Parameters**
- **param1**: Description of param1
- **param2**: Description of param2

**Returns**
    The processed result

**Raises**
    ValueError: When something is wrong"""
    assert convert_to_md(docstring) == expected.strip()
