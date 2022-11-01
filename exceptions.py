class HTTPException(Exception):
  """
  HTTP exceptions raised
  """
  def __init__(self, code=500, message="Internal Server Error"):
    self.code = code
    self.message = message
    super().__init__(f'{self.code} {self.message}')

  def __str__(self):
    return f"{self.code} {self.message}"
