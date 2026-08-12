

class MinhaExcecao(Exception):
    def __init__(self, mensagem_erro: str):
        self.mensagem_erro = mensagem_erro