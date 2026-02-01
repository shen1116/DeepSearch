import dotenv
dotenv.load_dotenv()

from src.graph import create_graph
if __name__ == "__main__":
    graph = create_graph()
    result = graph.invoke({
        "user_input": "Test the subagents, let them use tools to get the information"
    })
    print(result)