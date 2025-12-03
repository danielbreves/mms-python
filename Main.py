import enum
from dataclasses import dataclass, field
from typing import NamedTuple
import API
import sys


class Direction(enum.Enum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    @staticmethod
    def getLeft(direction: "Direction") -> "Direction":
        return Direction((direction.value - 1) % 4)

    @staticmethod
    def getRight(direction: "Direction") -> "Direction":
        return Direction((direction.value + 1) % 4)

    @staticmethod
    def toStr(direction: "Direction") -> str:
        return direction.name[0].lower()


class Position(NamedTuple):
    x: int
    y: int

    def move(self, direction: Direction) -> "Position":
        offset = NextCellOffset[direction]
        return Position(self.x + offset[0], self.y + offset[1])


NextCellOffset = {
    Direction.NORTH: (0, 1),
    Direction.EAST: (1, 0),
    Direction.SOUTH: (0, -1),
    Direction.WEST: (-1, 0),
}


@dataclass
class MazeCell:
    walls: dict[Direction, bool] = field(
        default_factory=lambda: {d: False for d in Direction}
    )
    visited: bool = False

    def setWall(self, direction: Direction, has_wall: bool):
        self.walls[direction] = has_wall


class Maze:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = [[MazeCell() for _ in range(width)] for _ in range(height)]

    def isValidPosition(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def getCell(self, pos: Position) -> MazeCell:
        if not self.isValidPosition(pos):
            raise ValueError("Cell coordinates out of bounds")
        return self.grid[pos.y][pos.x]

    def setCellWall(self, pos: Position, direction: Direction, has_wall: bool):
        self.getCell(pos).setWall(direction, has_wall)


@dataclass
class Robot:
    position: Position = field(default_factory=lambda: Position(0, 0))
    direction: Direction = Direction.NORTH

    def turnLeft(self):
        API.turnLeft()
        self.direction = Direction.getLeft(self.direction)

    def turnRight(self):
        API.turnRight()
        self.direction = Direction.getRight(self.direction)

    def moveForward(self):
        API.moveForward()
        self.position = self.position.move(self.direction)


def log(string):
    sys.stderr.write("{}\n".format(string))
    sys.stderr.flush()


def setWall(maze: Maze, pos: Position, direction: Direction, has_wall: bool):
    if has_wall:
        API.setWall(pos.x, pos.y, Direction.toStr(direction))
    maze.setCellWall(pos, direction, has_wall)


def main():
    log("Running...")
    robot = Robot()
    width = API.mazeWidth()
    height = API.mazeHeight()
    maze = Maze(width, height)
    API.setColor(0, 0, "G")
    API.setText(0, 0, "abc")
    while True:
        log("At cell {}, facing {}".format(robot.position, robot.direction))

        if API.wallLeft():
            wall_left = Direction.getLeft(robot.direction)
            setWall(maze, robot.position, wall_left, True)
        else:
            robot.turnLeft()
            setWall(maze, robot.position, robot.direction, False)

        while API.wallFront():
            setWall(maze, robot.position, robot.direction, True)
            robot.turnRight()

        robot.moveForward()

if __name__ == "__main__":
    main()
