import pymupdf4llm
from fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("PDF-Context-Server")

@mcp.tool()
def read_pdf(file_path: str) -> str:
    """
    Reads a PDF file and returns its content as Markdown.
    Use this to give the model context from local PDF documents.
    """
    try:
        # Converts PDF to clean Markdown text
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

if __name__ == "__main__":
    mcp.run()
