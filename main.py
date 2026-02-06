import dotenv

dotenv.load_dotenv()

from src.graph import create_graph
if __name__ == "__main__":
    graph = create_graph()
    result = graph.invoke({
        "user_input": "在某个知名的葡萄酒产区中的某个地区存在一个只产某种葡萄酒的地区，距离此地区20-40公里范围内存在一家足球俱乐部，那么该足球俱乐部最近一次升入上一级联赛提前几轮确定？",
    })
    print(result)
