def valid_email(email):
    if email == "true":
        return True
    else:
        return False

def valid_token(token, tokens):
    if token in tokens:
        return tokens[token] == 'unused'
    return False
