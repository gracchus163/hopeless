def valid_token(token, tokens):
    if token in tokens:
        return tokens[token] == 'unused'
    return False
