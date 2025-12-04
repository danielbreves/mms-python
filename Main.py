from collections import deque
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import NamedTuple, Protocol
import API
import sys


class SimulatorAPI(Protocol):
    """Protocol for the micromouse simulator API."""

    def mazeWidth(self) -> int: ...
    def mazeHeight(self) -> int: ...
    def wallFront(self) -> bool: ...
    def wallLeft(self) -> bool: ...
    def wallRight(self) -> bool: ...
    def turnLeft(self) -> None: ...
    def turnRight(self) -> None: ...
    def moveForward(self) -> None: ...
    def setWall(self, x: int, y: int, direction: str) -> None: ...
    def setColor(self, x: int, y: int, color: str) -> None: ...
    def clearColor(self, x: int, y: int) -> None: ...
    def setText(self, x: int, y: int, text: str) -> None: ...


class Direction(enum.Enum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    def left(self) -> "Direction":
        return Direction((self.value - 1) % 4)

    def right(self) -> "Direction":
        return Direction((self.value + 1) % 4)

    def to_str(self) -> str:
        return self.name[0].lower()

    def opposite(self) -> "Direction":
        return Direction((self.value + 2) % 4)

    def offset(self) -> "Position":
        return DIRECTION_OFFSETS[self]

    @staticmethod
    def is_valid_offset(offset: "Position") -> bool:
        return offset in DIRECTION_OFFSETS.values()


class Position(NamedTuple):
    x: int
    y: int

    def get_move(self, direction: Direction) -> "Position":
        offset = direction.offset()
        return Position(self.x + offset.x, self.y + offset.y)


DIRECTION_OFFSETS: dict[Direction, Position] = {
    Direction.NORTH: Position(0, 1),
    Direction.EAST: Position(1, 0),
    Direction.SOUTH: Position(0, -1),
    Direction.WEST: Position(-1, 0),
}


@dataclass
class MazeCell:
    walls: dict[Direction, bool | None] = field(
        default_factory=lambda: {d: None for d in Direction}
    )
    visited: bool = False

    def set_wall(self, direction: Direction, has_wall: bool):
        self.walls[direction] = has_wall


class Maze:
    def __init__(self, width: int, height: int, api: SimulatorAPI):
        self.width = width
        self.height = height
        self.api = api
        self.grid = [[MazeCell() for _ in range(width)] for _ in range(height)]
        self._set_boundary_walls()

    def _set_boundary_walls(self):
        for x in range(self.width):
            self.grid[0][x].walls[Direction.SOUTH] = True
            self.grid[self.height - 1][x].walls[Direction.NORTH] = True
        for y in range(self.height):
            self.grid[y][0].walls[Direction.WEST] = True
            self.grid[y][self.width - 1].walls[Direction.EAST] = True

    def is_valid_position(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def get_cell(self, pos: Position) -> MazeCell:
        if not self.is_valid_position(pos):
            raise ValueError("Cell coordinates out of bounds")
        return self.grid[pos.y][pos.x]

    def _set_cell_wall(self, pos: Position, direction: Direction, has_wall: bool):
        self.get_cell(pos).set_wall(direction, has_wall)

    def set_wall(self, pos: Position, direction: Direction, has_wall: bool):
        """Set wall in maze and update the simulator display."""
        if has_wall:
            self.api.setWall(pos.x, pos.y, direction.to_str())
        self._set_cell_wall(pos, direction, has_wall)

        # Set wall in adjacent cell too
        adjacent_pos = pos.get_move(direction)
        if self.is_valid_position(adjacent_pos):
            opposite = direction.opposite()
            self._set_cell_wall(adjacent_pos, opposite, has_wall)


@dataclass
class Robot:
    api: SimulatorAPI
    position: Position = field(default_factory=lambda: Position(0, 0))
    direction: Direction = Direction.NORTH

    def has_wall_front(self) -> bool:
        return self.api.wallFront()

    def has_wall_left(self) -> bool:
        return self.api.wallLeft()

    def has_wall_right(self) -> bool:
        return self.api.wallRight()

    def turn_left(self):
        self.api.turnLeft()
        log("left")
        self.direction = self.direction.left()

    def turn_right(self):
        self.api.turnRight()
        log("right")
        self.direction = self.direction.right()

    def move_forward(self):
        self.api.moveForward()
        log("forward")
        self.position = self.position.get_move(self.direction)

    def turn_to_position(self, next_position: Position):
        """Turn to face an adjacent cell given its absolute position."""
        offset = Position(
            next_position.x - self.position.x, next_position.y - self.position.y
        )

        if offset == Position(0, 0) or offset == self.direction.offset():
            return

        if not Direction.is_valid_offset(offset):
            raise ValueError("Invalid target position - must be adjacent")

        if offset == self.direction.left().offset():
            self.turn_left()
        elif offset == self.direction.right().offset():
            self.turn_right()
        else:
            self.turn_right()
            self.turn_right()

    def move_to_position(self, next_position: Position):
        """Move to an adjacent cell given its absolute position."""
        if next_position == self.position:
            return

        self.turn_to_position(next_position)
        self.move_forward()

    def scan_walls(self, maze: "Maze"):
        """Scan and record walls in all visible directions."""
        maze.set_wall(self.position, self.direction, self.has_wall_front())
        maze.set_wall(self.position, self.direction.left(), self.has_wall_left())
        maze.set_wall(self.position, self.direction.right(), self.has_wall_right())


def log(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


class MazeSolver(ABC):
    """Abstract base class for maze solving algorithms."""

    def __init__(self, robot: Robot, maze: Maze, api: SimulatorAPI):
        self.robot = robot
        self.maze = maze
        self.api = api

    @abstractmethod
    def solve(self) -> list[Position]:
        """Explore the maze and return the path to the goal."""
        ...

    def is_goal(self, pos: Position) -> bool:
        """Check if position is in the center 2x2 goal area."""
        center_x = self.maze.width // 2
        center_y = self.maze.height // 2
        return pos.x in (center_x - 1, center_x) and pos.y in (center_y - 1, center_y)

    def return_to_start(self, path: list[Position]) -> None:
        """Navigate back to the starting position."""
        backtrack_path = deque(path)
        while backtrack_path:
            previous_pos = backtrack_path.pop()
            self.robot.move_to_position(previous_pos)

    def run_path(self, path: list[Position]) -> None:
        """Execute a path from current position."""
        log(f"Running path: {path}")
        for next_pos in path:
            self.robot.move_to_position(next_pos)


class DFSSolver(MazeSolver):
    """Depth-first search maze solver with backtracking."""

    def solve(self) -> list[Position]:
        """Explore the maze using DFS and return the path to goal."""
        path: list[Position] = []

        while True:
            if self.is_goal(self.robot.position):
                self._mark_goal_reached(path)
                return path

            self.robot.scan_walls(self.maze)

            unvisited_pos = self._find_unvisited_neighbor()
            if unvisited_pos:
                self.robot.turn_to_position(unvisited_pos)

            while self.robot.has_wall_front():
                self.maze.set_wall(self.robot.position, self.robot.direction, True)
                self.robot.turn_right()

            self.maze.set_wall(self.robot.position, self.robot.direction, False)
            self.maze.get_cell(self.robot.position).visited = True

            next_pos = self.robot.position.get_move(self.robot.direction)
            if not self.maze.get_cell(next_pos).visited:
                self._move_forward_on_path(path)
            else:
                if not self._backtrack(path):
                    return []

    def _find_unvisited_neighbor(self) -> Position | None:
        """Find an unvisited neighboring cell."""
        next_direction = self.robot.direction
        current_cell = self.maze.get_cell(self.robot.position)

        for _ in range(4):
            if current_cell.walls[next_direction] is not True:
                adjacent_pos = self.robot.position.get_move(next_direction)
                if (
                    self.maze.is_valid_position(adjacent_pos)
                    and not self.maze.get_cell(adjacent_pos).visited
                ):
                    return adjacent_pos
            next_direction = next_direction.left()

        return None

    def _move_forward_on_path(self, path: list[Position]) -> None:
        """Move forward and add current position to path."""
        path.append(self.robot.position)
        self.api.setColor(self.robot.position.x, self.robot.position.y, "G")
        self.robot.move_forward()

    def _backtrack(self, path: list[Position]) -> bool:
        """Backtrack to previous position. Returns False if path is empty."""
        if not path:
            log("No path to goal found!")
            return False

        previous_pos = path.pop()
        self.api.setColor(self.robot.position.x, self.robot.position.y, "B")
        self.robot.move_to_position(previous_pos)
        return True

    def _mark_goal_reached(self, path: list[Position]) -> None:
        """Mark goal cell and add to path."""
        path.append(self.robot.position)
        self.api.setColor(self.robot.position.x, self.robot.position.y, "G")
        self.api.setText(self.robot.position.x, self.robot.position.y, "end")
        log("Reached the end!")


def main():
    log("Running...")
    robot = Robot(api=API)
    maze = Maze(API.mazeWidth(), API.mazeHeight(), api=API)
    API.setText(0, 0, "start")

    solver = DFSSolver(robot, maze, api=API)
    path = solver.solve()
    if path:
        solver.return_to_start(path)
        solver.run_path(path)


if __name__ == "__main__":
    main()
