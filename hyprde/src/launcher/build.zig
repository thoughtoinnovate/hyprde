const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const exe = b.addExecutable(.{
        .name = "hyprsearch",
        .root_module = b.createModule(.{
            .target = target,
            .optimize = optimize,
        }),
    });

    exe.root_module.addCSourceFile(.{ .file = b.path("src/launcher.c"), .flags = &.{} });
    exe.root_module.addCSourceFile(.{ .file = b.path("src/toml.c"), .flags = &.{} });
    exe.root_module.link_libc = true;
    exe.root_module.linkSystemLibrary("gtk+-3.0", .{});
    exe.root_module.linkSystemLibrary("gtk-layer-shell-0", .{});
    exe.root_module.linkSystemLibrary("gio-2.0", .{});

    b.installArtifact(exe);
}
