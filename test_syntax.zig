const std = @import("std");
pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    const allocator = gpa.allocator();
    var list = std.ArrayList(u8){};
    defer list.deinit(allocator);
    try list.append(allocator, 1);
    std.debug.print("Size: {d}\n", .{list.items.len});
}
