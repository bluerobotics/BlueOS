from pydantic import BaseModel


class Extension(BaseModel):
    name: str
    docker: str
    tag: str
    permissions: str
    enabled: bool
    identifier: str
    user_permissions: str

    def is_valid(self) -> bool:
        return all([self.name, self.docker, self.tag, any([self.permissions, self.user_permissions]), self.identifier])
