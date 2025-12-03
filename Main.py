from collections import deque
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
    def get_left(direction: "Direction") -> "Direction":
        return Direction((direction.value - 1) % 4)

    @staticmethod
    def get_right(direction: "Direction") -> "Direction":
        return Direction((direction.value + 1) % 4)

    @staticmethod
    def to_str(direction: "Direction") -> str:
        return direction.name[0].lower()

    @staticmethod
    def get_opposite(direction: "Direction") -> "Direction":
        return Direction((direction.value + 2) % 4)


class Position(NamedTuple):
    x: int
    y: int

    def get_move(self, direction: Direction) -> "Position":
        offset = NextCellOffset[direction]
        return Position(self.x + offset.x, self.y + offset.y)


NextCellOffset: dict[Direction, Position] = {
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
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
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

    def set_cell_wall(self, pos: Position, direction: Direction, has_wall: bool):
        self.get_cell(pos).set_wall(direction, has_wall)

    def set_wall(self, pos: Position, direction: Direction, has_wall: bool):
        """Set wall in maze and update the simulator display."""
        if has_wall:
            API.setWall(pos.x, pos.y, Direction.to_str(direction))
        self.set_cell_wall(pos, direction, has_wall)

        # Set wall in adjacent cell too
        adjacent_pos = pos.get_move(direction)
        if self.is_valid_position(adjacent_pos):
            opposite = Direction.get_opposite(direction)
            self.set_cell_wall(adjacent_pos, opposite, has_wall)


@dataclass
class Robot:
    position: Position = field(default_factory=lambda: Position(0, 0))
    direction: Direction = Direction.NORTH

    def has_wall_front(self) -> bool:
        return API.wallFront()

    def has_wall_left(self) -> bool:
        return API.wallLeft()

    def has_wall_right(self) -> bool:
        return API.wallRight()

    def turn_left(self):
        API.turnLeft()
        log("left")
        self.direction = Direction.get_left(self.direction)

    def turn_right(self):
        API.turnRight()
        log("right")
        self.direction = Direction.get_right(self.direction)

    def move_forward(self):
        API.moveForward()
        log("forward")
        self.position = self.position.get_move(self.direction)

    def turn_to_position(self, next_position: Position):
        if (
            next_position == Position(0, 0)
            or next_position == NextCellOffset[self.direction]
        ):
            return

        if next_position not in NextCellOffset.values():
            raise ValueError("Invalid next position offset")

        if next_position == NextCellOffset[Direction.get_left(self.direction)]:
            self.turn_left()
        elif next_position == NextCellOffset[Direction.get_right(self.direction)]:
            self.turn_right()
        else:
            self.turn_right()
            self.turn_right()

    def move_to_position(self, next_position: Position):
        if next_position == Position(0, 0):
            return

        self.turn_to_position(next_position)
        self.move_forward()

    def scan_walls(self, maze: "Maze"):
        """Scan and record walls in all visible directions."""
        maze.set_wall(self.position, self.direction, self.has_wall_front())
        maze.set_wall(
            self.position, Direction.get_left(self.direction), self.has_wall_left()
        )
        maze.set_wall(
            self.position, Direction.get_right(self.direction), self.has_wall_right()
        )


def log(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def is_goal(pos: Position, width: int, height: int) -> bool:
    """Check if position is in the center 2x2 goal area."""
    center_x, center_y = width // 2, height // 2
    return pos.x in (center_x - 1, center_x) and pos.y in (center_y - 1, center_y)


def find_unvisited_neighbor(robot: Robot, maze: Maze) -> Direction | None:
    """Find an unvisited neighboring cell and turn toward it."""
    next_direction = robot.direction
    current_cell = maze.get_cell(robot.position)

    for _ in range(4):
        if current_cell.walls[next_direction] is not True:
            adjacent_pos = robot.position.get_move(next_direction)
            if (
                maze.is_valid_position(adjacent_pos)
                and not maze.get_cell(adjacent_pos).visited
            ):
                return next_direction
        next_direction = Direction.get_left(next_direction)

    return None


def move_forward_on_path(robot: Robot, maze: Maze, path: list[Position]) -> None:
    """Move forward and add current position to path."""
    path.append(robot.position)
    API.setColor(robot.position.x, robot.position.y, "G")
    robot.move_forward()


def backtrack(robot: Robot, path: list[Position]) -> bool:
    """Backtrack to previous position. Returns False if path is empty."""
    if not path:
        log("No path to goal found!")
        return False

    previous_pos = path.pop()
    next_position = Position(
        previous_pos.x - robot.position.x, previous_pos.y - robot.position.y
    )
    API.clearColor(robot.position.x, robot.position.y)
    robot.move_to_position(next_position)
    return True


def mark_goal_reached(robot: Robot, path: list[Position]) -> None:
    """Mark goal cell and add to path."""
    path.append(robot.position)
    API.setColor(robot.position.x, robot.position.y, "G")
    API.setText(robot.position.x, robot.position.y, "end")
    log("Reached the end!")


def explore_maze(robot: Robot, maze: Maze) -> list[Position]:
    """Explore the maze using DFS and return the path to goal."""
    path: list[Position] = []
    width, height = maze.width, maze.height

    while True:
        if is_goal(robot.position, width, height):
            mark_goal_reached(robot, path)
            return path

        robot.scan_walls(maze)

        unvisited_dir = find_unvisited_neighbor(robot, maze)
        if unvisited_dir:
            offset = NextCellOffset[unvisited_dir]
            robot.turn_to_position(offset)

        while robot.has_wall_front():
            maze.set_wall(robot.position, robot.direction, True)
            robot.turn_right()

        maze.set_wall(robot.position, robot.direction, False)
        maze.get_cell(robot.position).visited = True

        next_pos = robot.position.get_move(robot.direction)
        if not maze.get_cell(next_pos).visited:
            move_forward_on_path(robot, maze, path)
        else:
            if not backtrack(robot, path):
                return []


def return_to_start(robot: Robot, path: list[Position]) -> None:
    """Navigate back to the starting position."""
    backtrack_path = deque(path)

    while backtrack_path:
        previous_pos = backtrack_path.pop()
        next_position = Position(
            previous_pos.x - robot.position.x, previous_pos.y - robot.position.y
        )
        robot.move_to_position(next_position)


def run_fastest_path(robot: Robot, path: list[Position]) -> None:
    """Execute the fastest path from start to goal."""
    log(f"Running fastest path: {path}")

    for next_pos in path:
        next_position = Position(
            next_pos.x - robot.position.x, next_pos.y - robot.position.y
        )
        robot.move_to_position(next_position)


def main():
    log("Running...")
    robot = Robot()
    maze = Maze(API.mazeWidth(), API.mazeHeight())
    API.setText(0, 0, "start")

    path = explore_maze(robot, maze)
    if path:
        return_to_start(robot, path)
        run_fastest_path(robot, path)


if __name__ == "__main__":
    main()
