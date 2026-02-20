from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
def main():
    llm = ChatOpenAI(
                model='minimind',
                temperature=0.8,
                api_key="123",
                base_url="http://localhost:8998/v1",
            )
    agent = create_agent(llm)
    # print(agent.invoke({"messages": [{"role": "user", "content": "What is the meaning of life?"}]}))
    for chunk in agent.stream({"messages": [{"role": "user", "content": "帮我写一段快速排序的示例python代码,只提供给我python代码，不要解释"}]}):
        print(chunk)

if __name__ == "__main__":
    main()
    